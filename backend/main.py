import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .database import (
    init_db,
    insert_note,
    get_notes_for_address,
    get_all_address_stats,
    purge_address,
    count_all_notes,
    mark_conflict,
)
from .models import (
    DeliveryNoteCreate,
    DeliveryNote,
    BriefingResponse,
    DashboardResponse,
    AddressDashboardEntry,
    SeedResponse,
    ForgetResponse,
    TranscriptionResponse,
    ConfidenceLevel,
    RiskResponse,
    FeedbackRequest,
    FeedbackResponse,
    ConflictResponse,
)
from .memory import setup, remember, recall, improve, forget
from .agents import RiskAgent, FeedbackAgent, ConflictResolutionAgent
from .agents.feedback_agent import FeedbackRating

_risk_agent = RiskAgent(failed_cost=float(os.getenv("FAILED_DELIVERY_COST", "15.0")))
_feedback_agent = FeedbackAgent()
_conflict_agent = ConflictResolutionAgent()
from .seed_data import get_all_seed_notes, get_seed_addresses
from .transcribe import transcribe_audio, TranscriptionError

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("last_mile.api")

FAILED_COST = float(os.getenv("FAILED_DELIVERY_COST", "15.0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await setup()
    yield


app = FastAPI(
    title="Last Mile API",
    description="Persistent delivery-site memory — remember, recall, improve, forget.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "notes_in_db": count_all_notes()}


# ---------------------------------------------------------------------------
# remember() — driver logs a delivery note
# ---------------------------------------------------------------------------

@app.post("/notes", response_model=DeliveryNote, status_code=201)
async def log_note(payload: DeliveryNoteCreate, background: BackgroundTasks):
    """
    Capture a post-delivery note. Ingests into Cognee immediately;
    triggers improve() (cognify) in the background so we don't block the driver.
    """
    ts = payload.timestamp or datetime.utcnow()
    note_dict = {
        **payload.model_dump(),
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
    }

    note_id = insert_note(note_dict)
    await remember(note_dict)

    # Kick off improve() asynchronously — expensive LLM graph-building step
    background.add_task(_background_improve, payload.address_id)

    return DeliveryNote(id=note_id, **{**payload.model_dump(), "timestamp": ts})


async def _background_improve(address_id: str):
    try:
        await improve(address_id)
    except Exception as e:
        logger.error("Background improve() failed for %s: %s", address_id, e)


# ---------------------------------------------------------------------------
# Voice-note transcription — driver speaks instead of types
# ---------------------------------------------------------------------------

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(audio: UploadFile = File(...)):
    """
    Accept a short audio clip recorded in the driver app and return transcribed
    text to prefill the note field. Independent of the LLM_PROVIDER used for
    the memory graph — always uses Whisper via OPENAI_API_KEY/WHISPER_API_KEY.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "No audio data received.")

    try:
        text = await transcribe_audio(audio_bytes, filename=audio.filename or "note.wav")
    except TranscriptionError as e:
        raise HTTPException(502, f"Transcription unavailable: {e}")

    return TranscriptionResponse(text=text)


# ---------------------------------------------------------------------------
# recall() — driver requests pre-arrival briefing
# ---------------------------------------------------------------------------

@app.get("/briefing/{address_id}", response_model=BriefingResponse)
async def get_briefing(address_id: str, address_text: str = ""):
    """
    Return a synthesized briefing for the driver before they depart.
    address_text is used for cold-start similarity search if no history exists.
    """
    if not address_text:
        notes = get_notes_for_address(address_id)
        address_text = notes[0]["address_text"] if notes else address_id.replace("_", " ")

    result = await recall(address_id, address_text)
    return BriefingResponse(**result)


# ---------------------------------------------------------------------------
# improve() — explicit reconciliation trigger (ops / admin)
# ---------------------------------------------------------------------------

@app.post("/improve/{address_id}")
async def trigger_improve(address_id: str):
    """
    Trigger graph-building and conflict reconciliation for a specific address.
    Normally runs in the background after each note; this is the manual trigger.
    """
    notes = get_notes_for_address(address_id)
    if not notes:
        raise HTTPException(404, f"No notes found for address '{address_id}'")

    await improve(address_id)
    return {"address_id": address_id, "message": "Memory graph updated.", "notes_processed": len(notes)}


# ---------------------------------------------------------------------------
# forget() — privacy / data-retention purge
# ---------------------------------------------------------------------------

@app.delete("/forget/{address_id}", response_model=ForgetResponse)
async def forget_address(address_id: str):
    """
    Purge all memory for an address — both the Cognee graph and the SQLite records.
    Use for customer privacy requests or data-retention compliance.
    """
    notes = get_notes_for_address(address_id)
    if not notes:
        raise HTTPException(404, f"No data found for address '{address_id}'")

    await forget(address_id)
    count = purge_address(address_id)

    return ForgetResponse(
        address_id=address_id,
        message=f"All memory for this address has been purged.",
        notes_purged=count,
    )


# ---------------------------------------------------------------------------
# Ops dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_model=DashboardResponse)
async def dashboard():
    """
    Aggregate view for delivery-ops: which addresses cost the most, what the
    system has learned, and estimated cost avoided by memory-assisted deliveries.
    """
    rows = get_all_address_stats()
    entries = []
    total_deliveries = 0
    total_failed = 0
    total_cost_avoided = 0.0

    for row in rows:
        total = row["total"]
        failed = row["failed"]
        failure_rate = (failed / total) if total > 0 else 0.0
        cost_at_risk = failed * FAILED_COST

        # Cost avoided: assume memory helps on ~60% of successful attempts
        # (conservative estimate for the pitch)
        successful_with_memory = (total - failed)
        cost_avoided = successful_with_memory * 0.6 * FAILED_COST if total > 3 else 0.0

        notes = get_notes_for_address(row["address_id"])
        confidence = _derive_confidence_sync(notes)

        entry = AddressDashboardEntry(
            address_id=row["address_id"],
            address_text=row["address_text"],
            total_deliveries=total,
            failed_deliveries=failed,
            failure_rate=round(failure_rate, 3),
            cost_at_risk=round(cost_at_risk, 2),
            cost_avoided=round(cost_avoided, 2),
            has_memory=total > 0,
            confidence=confidence,
            last_delivery=datetime.fromisoformat(row["last_delivery"]) if row["last_delivery"] else None,
            conflicts_detected=row["conflicts"],
        )
        entries.append(entry)
        total_deliveries += total
        total_failed += failed
        total_cost_avoided += cost_avoided

    return DashboardResponse(
        total_addresses=len(entries),
        total_deliveries=total_deliveries,
        total_failed=total_failed,
        overall_failure_rate=round(total_failed / total_deliveries, 3) if total_deliveries else 0.0,
        total_cost_avoided=round(total_cost_avoided, 2),
        addresses=sorted(entries, key=lambda e: e.failure_rate, reverse=True),
    )


def _derive_confidence_sync(notes: list[dict]) -> ConfidenceLevel:
    from datetime import timedelta
    from .memory import STALE_DAYS

    if not notes:
        return ConfidenceLevel.COLD_START
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=STALE_DAYS)
    recent = [n for n in notes if datetime.fromisoformat(n["timestamp"]) > stale_cutoff]
    if not recent:
        return ConfidenceLevel.LOW
    drivers = len(set(n["driver_id"] for n in recent))
    if drivers >= 3 and len(recent) >= 3:
        return ConfidenceLevel.HIGH
    elif drivers >= 2 or len(recent) >= 3:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Seed endpoint — loads demo data
# ---------------------------------------------------------------------------

@app.post("/seed", response_model=SeedResponse)
async def seed_demo_data(background: BackgroundTasks):
    """
    Load the synthetic demo dataset. Safe to call multiple times (idempotent on address_id).
    Triggers improve() for each address in the background after ingestion.
    """
    notes = get_all_seed_notes()
    ingested = 0

    for note in notes:
        insert_note(note)
        await remember(note)
        ingested += 1

    addresses = get_seed_addresses()
    for addr in addresses:
        background.add_task(_background_improve, addr["address_id"])

    return SeedResponse(
        message="Demo data loaded. Memory graphs building in the background.",
        notes_ingested=ingested,
        addresses_seeded=len(addresses),
    )


# ---------------------------------------------------------------------------
# Agent 2: Pre-dispatch risk assessment
# ---------------------------------------------------------------------------

@app.get("/risk/{address_id}", response_model=RiskResponse)
async def get_risk(address_id: str, address_text: str = "", hour: int | None = None):
    """
    Risk Agent: assesses delivery risk before dispatch.
    Pass ?hour=14 (24h) for time-aware risk scoring.
    """
    notes = get_notes_for_address(address_id)
    if not address_text and notes:
        address_text = notes[0]["address_text"]
    elif not address_text:
        address_text = address_id.replace("_", " ")

    from .database import get_conn
    conn = get_conn()
    row = conn.execute(
        "SELECT conflicts FROM address_meta WHERE address_id=?", (address_id,)
    ).fetchone()
    conn.close()
    conflict_flag = row["conflicts"] if row else 0

    assessment = await _risk_agent.run(
        address_id=address_id,
        address_text=address_text,
        notes=notes,
        planned_hour=hour,
        conflict_flag=conflict_flag,
    )
    return RiskResponse(**assessment.__dict__)


# ---------------------------------------------------------------------------
# Agent 4: Driver feedback loop
# ---------------------------------------------------------------------------

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest):
    """
    Feedback Agent: driver rates the briefing after delivery.
    - accurate   → improve() reinforces the knowledge graph
    - inaccurate → LLM generates correction → stored via remember()
    - partial    → correction flagged for review
    """
    try:
        rating = FeedbackRating(payload.rating)
    except ValueError:
        raise HTTPException(400, f"rating must be one of: accurate, inaccurate, partial")

    result = await _feedback_agent.run(
        address_id=payload.address_id,
        address_text=payload.address_text,
        rating=rating,
        original_briefing=payload.original_briefing,
        driver_comment=payload.driver_comment,
        driver_id=payload.driver_id,
        driver_name=payload.driver_name,
    )
    return FeedbackResponse(**result.__dict__)


# ---------------------------------------------------------------------------
# Agent 1: On-demand conflict resolution
# ---------------------------------------------------------------------------

@app.post("/resolve/{address_id}", response_model=ConflictResponse)
async def resolve_conflicts(address_id: str, address_text: str = ""):
    """
    Conflict Resolution Agent: explicitly run LLM-based conflict analysis
    for an address and store the resolution into Cognee.
    """
    notes = get_notes_for_address(address_id)
    if not notes:
        raise HTTPException(404, f"No notes found for address '{address_id}'")
    if not address_text:
        address_text = notes[0]["address_text"]

    verdict = await _conflict_agent.run(address_id, address_text, notes)
    if verdict.has_conflict:
        mark_conflict(address_id)

    return ConflictResponse(
        address_id=address_id,
        has_conflict=verdict.has_conflict,
        conflicting_facts=verdict.conflicting_facts,
        resolved_truth=verdict.resolved_truth,
        reasoning=verdict.reasoning,
        confidence=verdict.confidence,
    )


# ---------------------------------------------------------------------------
# Address listing helper (for frontend dropdowns)
# ---------------------------------------------------------------------------

@app.get("/addresses")
def list_addresses():
    rows = get_all_address_stats()
    known = [{"address_id": r["address_id"], "address_text": r["address_text"]} for r in rows]
    # Include the cold-start address always
    cold = {"address_id": "500_pine_blvd", "address_text": "500 Pine Boulevard, Springfield"}
    if not any(a["address_id"] == "500_pine_blvd" for a in known):
        known.append(cold)
    return known

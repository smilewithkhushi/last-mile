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
    LandmarkResolveRequest,
    LandmarkResolveResponse,
    ConfidenceLevel,
)
from .memory import setup, remember, recall, improve, forget
from .seed_data import get_all_seed_notes, get_seed_addresses
from .transcribe import transcribe_audio, TranscriptionError
from .landmarks import resolve_landmark

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
# Landmark-based addressing — for deliveries with no formal address at all
# ---------------------------------------------------------------------------

@app.post("/landmarks/resolve", response_model=LandmarkResolveResponse)
def resolve_landmark_endpoint(payload: LandmarkResolveRequest):
    """
    Resolve a free-text landmark description ("near the temple, ask for
    Salim's house") to an address_id — reusing an existing cluster if a
    semantically similar description was seen before, otherwise creating a
    new one. The returned address_id/address_text plug directly into the
    existing /notes and /briefing endpoints, same as a formal address.
    """
    if not payload.description.strip():
        raise HTTPException(400, "Landmark description cannot be empty.")
    return LandmarkResolveResponse(**resolve_landmark(payload.description, force_new=payload.force_new))


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

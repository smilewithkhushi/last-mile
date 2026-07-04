"""
StreetSense memory layer — uses Cognee 1.x native remember/recall/improve/forget.

Each address gets its own Cognee dataset (named by address_id). Notes are stored
as rich-text documents. recall() searches that graph for a synthesized briefing.
improve() triggers graph-building/conflict resolution. forget() purges the dataset.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import cognee
from cognee.infrastructure.llm.config import get_llm_config
from dotenv import load_dotenv

from .database import (
    get_notes_for_address,
    update_cognified,
    mark_conflict,
)
from .models import ConfidenceLevel

load_dotenv()
logger = logging.getLogger("streetsense.memory")

STALE_DAYS = int(os.getenv("STALE_NOTE_DAYS", "30"))
GLOBAL_DATASET = "streetsense_global"  # cross-address similarity for cold-start


def _configure_cognee():
    """
    Cognee reads LLM config from env vars via pydantic-settings.
    We just make sure the relevant vars are set from our .env.
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
    else:
        api_key = os.getenv("OPENAI_API_KEY", "")

    # Set env vars so Cognee's pydantic-settings picks them up
    os.environ.setdefault("LLM_PROVIDER", provider)
    os.environ.setdefault("LLM_MODEL", model)
    os.environ.setdefault("LLM_API_KEY", api_key)

    # Also set provider-specific keys
    if provider == "anthropic":
        os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
    else:
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    logger.info("Cognee configured. Provider: %s, Model: %s", provider, model)


def _format_note_as_document(note: dict) -> str:
    """Rich text document — Cognee extracts entities and relationships from this."""
    ts = note.get("timestamp", "unknown date")
    status_map = {
        "SUCCESS": "successful delivery",
        "FAILED": "failed delivery attempt",
        "PARTIAL": "partial delivery (left at door or with neighbor)",
    }
    status_label = status_map.get(note.get("status", ""), "delivery")

    return (
        f"Delivery Report for {note['address_text']}\n"
        f"Date: {ts}\n"
        f"Driver: {note['driver_name']} (ID: {note['driver_id']})\n"
        f"Outcome: {status_label}\n"
        f"Driver note: {note['note_text']}\n"
    )


def _derive_confidence(notes: list[dict]) -> ConfidenceLevel:
    if not notes:
        return ConfidenceLevel.COLD_START

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=STALE_DAYS)
    recent = [n for n in notes if datetime.fromisoformat(n["timestamp"]) > stale_cutoff]

    if not recent:
        return ConfidenceLevel.LOW

    unique_drivers = len(set(n["driver_id"] for n in recent))
    if unique_drivers >= 3 and len(recent) >= 3:
        return ConfidenceLevel.HIGH
    elif unique_drivers >= 2 or len(recent) >= 3:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _detect_conflicts(notes: list[dict]) -> bool:
    """Heuristic: flag if recent notes contain contradictory sentiment about the same feature."""
    if len(notes) < 2:
        return False
    contradiction_pairs = [
        ("buzzer broken", "buzzer works"),
        ("buzzer broken", "buzzer fixed"),
        ("gate locked", "gate open"),
        ("no one home", "always home"),
    ]
    texts = [n["note_text"].lower() for n in notes[-6:]]
    for pos, neg in contradiction_pairs:
        if any(pos in t for t in texts) and any(neg in t for t in texts):
            return True
    return False


# ---------------------------------------------------------------------------
# Public lifecycle API
# ---------------------------------------------------------------------------

async def setup():
    """Call once at startup to configure Cognee."""
    _configure_cognee()


async def remember(note: dict):
    """
    Ingest a delivery note into Cognee — stored in the address-specific dataset
    AND the global dataset (for cross-address cold-start similarity).
    Uses `self_improvement=True` so Cognee builds graph context automatically.
    """
    address_id = note["address_id"]
    doc = _format_note_as_document(note)

    try:
        # Per-address dataset
        await cognee.remember(doc, dataset_name=address_id, self_improvement=True)
        # Global dataset for cold-start similarity
        await cognee.remember(doc, dataset_name=GLOBAL_DATASET, self_improvement=False)
        logger.info("remember() — note stored for %s", address_id)
    except Exception as e:
        logger.error("remember() failed for %s: %s", address_id, e)
        raise


async def improve(address_id: str):
    """
    Explicitly trigger Cognee's graph-building and reconciliation for an address.
    `improve()` in Cognee 1.x does a deeper memification pass — resolves entity
    conflicts and strengthens edges between confirmed facts.
    """
    try:
        await cognee.improve(dataset=address_id)
        update_cognified(address_id)

        notes = get_notes_for_address(address_id)
        if _detect_conflicts(notes):
            mark_conflict(address_id)
            logger.info("improve() — conflict flagged at %s", address_id)

        logger.info("improve() — graph updated for %s", address_id)
    except Exception as e:
        logger.error("improve() failed for %s: %s", address_id, e)
        raise


async def recall(address_id: str, address_text: str) -> dict:
    """
    Return a synthesized pre-arrival briefing for the driver.
    Falls back to cross-address similarity if the address has no history.
    """
    notes = get_notes_for_address(address_id)
    confidence = _derive_confidence(notes)

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=STALE_DAYS)
    is_stale = bool(notes) and all(
        datetime.fromisoformat(n["timestamp"]) < stale_cutoff for n in notes
    )

    total_visits = len(notes)
    failed_visits = sum(1 for n in notes if n.get("status") == "FAILED")
    last_visit = (
        datetime.fromisoformat(max(n["timestamp"] for n in notes)) if notes else None
    )

    if confidence == ConfidenceLevel.COLD_START:
        briefing, key_facts = await _cold_start_briefing(address_text)
    else:
        briefing, key_facts = await _semantic_briefing(address_id, address_text, notes, confidence)

    return {
        "address_id": address_id,
        "address_text": address_text,
        "briefing": briefing,
        "confidence": confidence,
        "total_visits": total_visits,
        "failed_visits": failed_visits,
        "last_visit": last_visit,
        "key_facts": key_facts,
        "is_stale": is_stale,
    }


async def _semantic_briefing(
    address_id: str,
    address_text: str,
    notes: list[dict],
    confidence: ConfidenceLevel,
) -> tuple[str, list[str]]:
    query = (
        f"What do delivery drivers need to know before arriving at {address_text}? "
        "Include access instructions, door codes, hazards, timing restrictions, and any special notes."
    )
    try:
        results = await cognee.recall(
            query_text=query,
            datasets=[address_id],
        )
        if results:
            facts = _extract_facts_from_results(results)
            if facts:
                return _format_briefing(facts, confidence, notes), facts
    except Exception as e:
        logger.warning("Cognee recall fell back to rule-based for %s: %s", address_id, e)

    return _rule_based_briefing(notes, confidence)


async def _cold_start_briefing(address_text: str) -> tuple[str, list[str]]:
    """Similarity search across all known addresses for pattern-based guidance."""
    query = (
        f"What are common access issues, entry codes, and delivery tips for addresses similar to: {address_text}"
    )
    try:
        results = await cognee.recall(
            query_text=query,
            datasets=[GLOBAL_DATASET],
        )
        if results:
            facts = _extract_facts_from_results(results)[:3]
            if facts:
                briefing = (
                    "No prior delivery history for this address. "
                    "Based on similar locations in this network:\n"
                    + "\n".join(f"• {f}" for f in facts)
                )
                return briefing, facts
    except Exception as e:
        logger.warning("Cold-start recall failed: %s", e)

    return (
        "No prior delivery history for this address. "
        "Proceed with standard approach — attempt buzzer/intercom, leave a card if no answer, "
        "check for a safe-drop location.",
        ["No prior history — standard protocol applies"],
    )


def _extract_facts_from_results(results: list) -> list[str]:
    """Extract readable strings from Cognee recall response objects."""
    facts = []
    for r in results[:5]:
        try:
            # Cognee 1.x recall returns typed objects — get the answer/text field
            if hasattr(r, "answer"):
                facts.append(str(r.answer).strip())
            elif hasattr(r, "text"):
                facts.append(str(r.text).strip())
            elif hasattr(r, "content"):
                facts.append(str(r.content).strip())
            else:
                val = str(r).strip()
                if val and val != "None":
                    facts.append(val)
        except Exception:
            continue
    return [f for f in facts if f and len(f) > 5]


def _format_briefing(facts: list[str], confidence: ConfidenceLevel, notes: list[dict]) -> str:
    labels = {
        ConfidenceLevel.HIGH: "Confirmed by multiple drivers",
        ConfidenceLevel.MEDIUM: "Reported by 2+ drivers",
        ConfidenceLevel.LOW: "Reported once — treat with caution",
        ConfidenceLevel.COLD_START: "No prior history",
    }
    total = len(notes)
    failed = sum(1 for n in notes if n.get("status") == "FAILED")
    success_rate = f"{((total - failed) / total * 100):.0f}%" if total > 0 else "N/A"

    header = f"[{labels[confidence]} | {total} visits | {success_rate} success rate]\n\n"
    body = "\n".join(f"• {f}" for f in facts)
    return header + body


def _rule_based_briefing(notes: list[dict], confidence: ConfidenceLevel) -> tuple[str, list[str]]:
    """Fallback when Cognee returns nothing — summarise the most recent notes directly."""
    recent = sorted(notes, key=lambda n: n["timestamp"], reverse=True)[:5]
    key_facts = [n["note_text"] for n in recent]
    labels = {
        ConfidenceLevel.HIGH: "High confidence",
        ConfidenceLevel.MEDIUM: "Medium confidence",
        ConfidenceLevel.LOW: "Single report — unverified",
        ConfidenceLevel.COLD_START: "No history",
    }
    total = len(notes)
    failed = sum(1 for n in notes if n.get("status") == "FAILED")
    header = f"[{labels[confidence]} | {total} visits | {total - failed} successful]\n\n"
    body = "\n".join(f"• {n['note_text']}" for n in recent)
    return header + body, key_facts


async def forget(address_id: str):
    """
    Purge all Cognee memory for an address dataset.
    Called for privacy/compliance purge requests.
    """
    try:
        await cognee.forget(dataset=address_id)
        logger.info("forget() — dataset purged for %s", address_id)
    except Exception as e:
        logger.error("forget() failed for %s: %s", address_id, e)
        raise

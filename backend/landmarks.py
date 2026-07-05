"""
Landmark-based addressing — for deliveries with no formal address at all
("near the temple, ask for Salim's house near Pasha's shop"), which is the
harder, less-served version of the last-mile problem versus ambiguous-but-
existing formal addresses in cities.

A landmark description is resolved to an address_id by embedding it and
comparing against every previously seen landmark description. A close match
reuses the existing cluster (so "near the temple" and "behind the temple,
past the tea stall" from two different drivers collapse onto the same
memory); anything below the threshold becomes a brand-new cluster.

This runs independently of Cognee's own embedding pipeline — it's a small,
self-contained similarity search over a handful of stored vectors, not
something that needs a vector database.
"""

import json
import logging
import os
import re
import uuid
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from .database import get_all_landmarks, insert_landmark

logger = logging.getLogger("last_mile.landmarks")

LANDMARK_EMBEDDING_MODEL = os.getenv(
    "LANDMARK_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
# Two-tier thresholds, not one hard cutoff — calibrated against paraphrase/
# cross-lingual test pairs (e.g. "near the temple" vs "Shiv Mandir ke paas").
# Same-place paraphrases and different-place descriptions scored within ~0.02
# of each other around 0.55-0.60, too close for a single reliable cutoff on a
# small on-device model. A wrong auto-merge (pointing a driver at the wrong
# physical location) is worse than a missed one, so: only auto-merge above
# AUTO_MATCH_THRESHOLD; between the two thresholds, surface it as a
# non-blocking "possible match" instead of silently deciding either way.
AUTO_MATCH_THRESHOLD = float(os.getenv("LANDMARK_AUTO_MATCH_THRESHOLD", "0.65"))
SUGGEST_THRESHOLD = float(os.getenv("LANDMARK_SUGGEST_THRESHOLD", "0.45"))


@lru_cache
def _get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=LANDMARK_EMBEDDING_MODEL)


def _embed(text: str) -> np.ndarray:
    vec = next(_get_embedder().embed([text]))
    return np.asarray(vec)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def _new_landmark_id(description: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")[:30]
    return f"landmark_{slug}_{uuid.uuid4().hex[:6]}"


def resolve_landmark(description: str, force_new: bool = False) -> dict:
    """
    Resolve free-text landmark description to an address_id.

    Three outcomes:
    - Confident match (similarity >= AUTO_MATCH_THRESHOLD): reuse the existing
      cluster immediately, no confirmation needed.
    - Ambiguous (SUGGEST_THRESHOLD <= similarity < AUTO_MATCH_THRESHOLD) and
      not force_new: don't guess — return needs_confirmation=True with the
      candidate match, and persist nothing yet. The caller should ask "is this
      the same place?" and either reuse possible_match's address_id (yes) or
      call again with force_new=True (no).
    - New (similarity < SUGGEST_THRESHOLD, or force_new=True): persist as a
      new cluster.

    Returns:
        {
            "address_id": str | None,   # None only when needs_confirmation
            "address_text": str | None,
            "is_new": bool,
            "needs_confirmation": bool,
            "matched_description": str | None,   # confident auto-match, if any
            "similarity": float | None,           # similarity for the auto-match
            "possible_match": {"address_id", "description", "similarity"} | None,
        }
    """
    description = description.strip()
    query_vec = _embed(description)

    existing = get_all_landmarks()
    best_match = None
    best_score = -1.0

    for row in existing:
        candidate_vec = np.asarray(json.loads(row["embedding"]))
        score = _cosine_similarity(query_vec, candidate_vec)
        if score > best_score:
            best_score = score
            best_match = row

    if best_match is not None and best_score >= AUTO_MATCH_THRESHOLD:
        logger.info(
            "Landmark auto-matched existing cluster '%s' (similarity %.2f)",
            best_match["address_id"],
            best_score,
        )
        return {
            "address_id": best_match["address_id"],
            "address_text": best_match["description"],
            "is_new": False,
            "needs_confirmation": False,
            "matched_description": best_match["description"],
            "similarity": round(best_score, 3),
            "possible_match": None,
        }

    if best_match is not None and best_score >= SUGGEST_THRESHOLD and not force_new:
        logger.info(
            "Landmark ambiguous for '%s' — possible match with '%s' (similarity %.2f), asking for confirmation",
            description,
            best_match["address_id"],
            best_score,
        )
        return {
            "address_id": None,
            "address_text": None,
            "is_new": False,
            "needs_confirmation": True,
            "matched_description": None,
            "similarity": None,
            "possible_match": {
                "address_id": best_match["address_id"],
                "description": best_match["description"],
                "similarity": round(best_score, 3),
            },
        }

    address_id = _new_landmark_id(description)
    insert_landmark(address_id, description, json.dumps(query_vec.tolist()))
    logger.info("Landmark created new cluster '%s' (best prior similarity %.2f)", address_id, best_score)
    return {
        "address_id": address_id,
        "address_text": description,
        "is_new": True,
        "needs_confirmation": False,
        "matched_description": None,
        "similarity": None,
        "possible_match": None,
    }

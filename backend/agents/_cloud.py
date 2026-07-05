"""
Cognee Cloud session writer.

When agents produce a resolution or correction, they call cloud_remember() here
so the run is attributed to a named session and appears in the Cognee Cloud
dashboard under Sessions → Agent runs.

The main delivery-note remember/recall pipeline stays on the local SDK.
This module handles only agent-authored writes that need cloud visibility.
"""

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger("last_mile.agents.cloud")

_BASE_URL = os.getenv(
    "COGNEE_BASE_URL",
    "https://tenant-fc429b4b-c4dd-489e-8165-43574c815716.aws.cognee.ai",
).rstrip("/")
_API_KEY = os.getenv("COGNEE_API_KEY", "")
_DATASET = "default_dataset"
_TIMEOUT = 60.0


def _make_session_id(agent_name: str, address_id: str) -> str:
    date = datetime.utcnow().strftime("%Y%m%d")
    safe_addr = address_id[:20].replace(" ", "_")
    return f"{agent_name}-{safe_addr}-{date}"


async def cloud_remember(
    content: str,
    agent_name: str,
    address_id: str,
    filename: str | None = None,
) -> bool:
    """
    POST content to Cognee Cloud with a session_id so it appears in the
    Sessions dashboard. Returns True on success, False on failure (non-fatal).
    """
    if not _API_KEY:
        logger.warning("COGNEE_API_KEY not set — skipping cloud session write")
        return False

    session_id = _make_session_id(agent_name, address_id)
    fname = filename or f"{agent_name}_{address_id}.md"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_BASE_URL}/api/v1/remember",
                headers={"X-Api-Key": _API_KEY},
                data={
                    "datasetName": _DATASET,
                    "session_id": session_id,
                },
                files={"data": (fname, content.encode(), "text/markdown")},
            )
            resp.raise_for_status()
            logger.info(
                "cloud_remember: session=%s status=%s",
                session_id, resp.json().get("status", "?"),
            )
            return True
    except Exception as e:
        logger.warning("cloud_remember failed (non-fatal): %s", e)
        return False

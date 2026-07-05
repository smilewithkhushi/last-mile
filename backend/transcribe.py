"""
Voice-note transcription — turns a short audio clip from the driver into text
for the delivery note, so drivers can speak instead of type between stops.

Two providers are supported, selected via TRANSCRIPTION_PROVIDER:
  - "openai" (default): OpenAI's Whisper API directly (independent of whichever
    LLM_PROVIDER is configured for Cognee), since it's the most broadly available
    hosted speech-to-text option regardless of which chat-model provider the
    memory layer itself is using.
  - "whisper-api": https://whisper-api.com — a third-party async transcription
    service. Submitting a file returns a queued task_id; the result has to be
    polled for via GET /status/{task_id} until status flips to "completed".
"""

import asyncio
import logging
import os

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger("last_mile.transcribe")

TRANSCRIPTION_PROVIDER = os.getenv("TRANSCRIPTION_PROVIDER", "openai").lower()
TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "whisper-1")

WHISPER_API_BASE_URL = os.getenv("WHISPER_API_BASE_URL", "https://api.whisper-api.com")
WHISPER_API_POLL_INTERVAL = float(os.getenv("WHISPER_API_POLL_INTERVAL", "2"))
WHISPER_API_POLL_TIMEOUT = float(os.getenv("WHISPER_API_POLL_TIMEOUT", "60"))


class TranscriptionError(Exception):
    pass


async def transcribe_audio(audio_bytes: bytes, filename: str = "note.wav") -> str:
    if TRANSCRIPTION_PROVIDER == "whisper-api":
        return await _transcribe_via_whisper_api(audio_bytes, filename)
    return await _transcribe_via_openai(audio_bytes, filename)


async def _transcribe_via_openai(audio_bytes: bytes, filename: str) -> str:
    # WHISPER_API_KEY is reserved for the whisper-api.com provider (see
    # _transcribe_via_whisper_api) — don't fall back to it here, or a
    # whisper-api.com key gets sent to OpenAI's real API and fails auth.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-...":
        raise TranscriptionError(
            "No OPENAI_API_KEY configured for voice transcription. "
            "Set TRANSCRIPTION_PROVIDER=whisper-api to use WHISPER_API_KEY instead."
        )

    client = AsyncOpenAI(api_key=api_key)
    try:
        result = await client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=(filename, audio_bytes),
        )
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        raise TranscriptionError(str(e)) from e

    text = (result.text or "").strip()
    if not text:
        raise TranscriptionError("Transcription returned empty text.")
    return text


async def _transcribe_via_whisper_api(audio_bytes: bytes, filename: str) -> str:
    api_key = os.getenv("WHISPER_API_KEY")
    if not api_key:
        raise TranscriptionError(
            "No WHISPER_API_KEY configured for whisper-api.com transcription."
        )

    headers = {"X-API-Key": api_key}
    try:
        async with httpx.AsyncClient(base_url=WHISPER_API_BASE_URL, timeout=30) as client:
            submit_resp = await client.post(
                "/transcribe",
                headers=headers,
                files={"file": (filename, audio_bytes)},
            )
            submit_resp.raise_for_status()
            task = submit_resp.json()
            task_id = task["task_id"]

            elapsed = 0.0
            while elapsed < WHISPER_API_POLL_TIMEOUT:
                await asyncio.sleep(WHISPER_API_POLL_INTERVAL)
                elapsed += WHISPER_API_POLL_INTERVAL

                status_resp = await client.get(f"/status/{task_id}", headers=headers)
                status_resp.raise_for_status()
                status = status_resp.json()

                if status["status"] == "completed":
                    text = (status.get("result") or "").strip()
                    if not text:
                        raise TranscriptionError("Transcription returned empty text.")
                    return text
                if status["status"] == "failed":
                    raise TranscriptionError(f"whisper-api.com task failed: {status}")

            raise TranscriptionError(
                f"whisper-api.com transcription timed out after {WHISPER_API_POLL_TIMEOUT}s."
            )
    except httpx.HTTPError as e:
        logger.error("whisper-api.com transcription failed: %s", e)
        raise TranscriptionError(str(e)) from e

"""
Voice-note transcription — turns a short audio clip from the driver into text
for the delivery note, so drivers can speak instead of type between stops.

Uses OpenAI's Whisper API directly (independent of whichever LLM_PROVIDER is
configured for Cognee) since it's the most broadly available hosted speech-to-text
option regardless of which chat-model provider the memory layer itself is using.
"""

import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger("last_mile.transcribe")

TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "whisper-1")


class TranscriptionError(Exception):
    pass


async def transcribe_audio(audio_bytes: bytes, filename: str = "note.wav") -> str:
    api_key = os.getenv("WHISPER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-...":
        raise TranscriptionError(
            "No OPENAI_API_KEY (or WHISPER_API_KEY) configured for voice transcription."
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

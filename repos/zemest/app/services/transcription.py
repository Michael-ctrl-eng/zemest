"""Voice note transcription using faster-whisper (local, free)."""

import asyncio
import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_model = None
_model_lock = asyncio.Lock()


async def transcribe_url(url: str) -> str | None:
    """Download a voice note URL and transcribe it."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            tmp = Path(tempfile.mkstemp(suffix=".ogg")[1])
            tmp.write_bytes(resp.content)

            try:
                text = await asyncio.to_thread(_transcribe_file, str(tmp))
                return text
            finally:
                tmp.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Transcription failed: {e}")
        return None


def _transcribe_file(path: str) -> str | None:
    """Transcribe a local audio file using faster-whisper."""
    global _model

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper not installed")
        return None

    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")

    try:
        segments, _info = _model.transcribe(
            path,
            language=None,
            vad_filter=True,
            beam_size=1,
        )
        parts = [seg.text.strip() for seg in segments]
        text = " ".join(p for p in parts if p)
        return text if text else None
    except Exception as e:
        logger.warning(f"Whisper transcription error: {e}")
        return None

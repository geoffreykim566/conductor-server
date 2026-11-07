"""Speech to text: one WAV phrase to OpenAI's transcription endpoint (STT_MODEL).
Why this model and the vocabulary prompt: README.md (Voice)."""
import io
import logging
import wave

import httpx

from app.core import config

log = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/audio/transcriptions"
# Spellings the model should prefer; the text so far follows it, so a phrase continues the last.
VOCAB = ("Logic Pro, Conductor, Smart Tempo, Flex Time, Flex Pitch, Channel EQ, ChromaVerb, "
         "Space Designer, Alchemy, Sampler, Drummer, Mastering Assistant, Stem Splitter, Step Sequencer, "
         "Live Loops, Quick Sampler, Pitch Correction, Bounce, Freeze, Track Stack, Summing Stack, "
         "compressor, threshold, ratio, attack, release, sidechain, bus, aux, send, gain staging, "
         "buffer size, latency, sample rate, plug-in, FabFilter, Valhalla, Soundtoys, Waves, iZotope.")
_PROMPT_CHARS = 900
_client = httpx.AsyncClient(timeout=config.STT_TIMEOUT_S)   # tests patch _client.post


class BadAudio(ValueError):
    """Not a PCM WAV we accept."""


class SttError(Exception):
    """The transcription call failed. `kind` as in the chat errors: down | busy | retry."""

    def __init__(self, kind: str, status: int | None, detail: str):
        super().__init__(f"{kind}: HTTP {status}: {detail}")
        self.kind, self.status = kind, status


def wav_seconds(data: bytes) -> float:
    """Duration from the WAV header (never trust the client's count)."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() not in (1, 2) or w.getsampwidth() != 2 or not 8000 <= w.getframerate() <= 48000:
                raise BadAudio("unsupported format")
            frames = w.getnframes()
            rate = w.getframerate()
    except (wave.Error, EOFError) as e:
        raise BadAudio(str(e)) from e
    if frames <= 0:
        raise BadAudio("empty")
    return frames / rate


def prompt_for(context: str) -> str:
    return (VOCAB + " " + (context or "").strip())[-_PROMPT_CHARS:]


async def transcribe(audio: bytes, context: str = "") -> tuple[str, float | None]:
    """(text, seconds OpenAI billed, when it says)."""
    try:
        r = await _client.post(
            URL,
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            data={"model": config.STT_MODEL, "prompt": prompt_for(context), "response_format": "json"},
            files={"file": ("phrase.wav", audio, "audio/wav")},
        )
    except httpx.TimeoutException as e:
        raise SttError("down", None, f"timeout {e!r}") from e
    except httpx.HTTPError as e:
        raise SttError("down", None, repr(e)) from e
    if r.status_code != 200:
        kind = "busy" if r.status_code == 429 else "retry" if r.status_code == 400 else "down"
        raise SttError(kind, r.status_code, r.text[:300])
    body = r.json()
    usage = body.get("usage") or {}
    billed = float(usage["seconds"]) if usage.get("type") == "duration" and usage.get("seconds") is not None else None
    return (body.get("text") or "").strip(), billed

"""Text to speech for the avatar. OWNER: Member 1. See plan.md §6.6.

Why this exists
---------------
SyncTalk generates a talking face from audio the *client* sends it. Nothing in
LearnQuest produced that audio, so the photoreal avatar rendered a face and
never spoke. This is the missing source.

Gemini is the natural provider here, and not only because `LLM_API_KEY` is
already a Gemini key: its TTS models return `audio/L16;codec=pcm;rate=24000` -
raw 16-bit PCM at 24 kHz, which is exactly the rate SyncTalk's feature extractor
works in (`SR = 24000` in avatar_server_ws.py). No resampling, no container to
unwrap, no format negotiation. Measured 2026-09-22 against the live API.

The rate is still read from the response rather than assumed: if a future model
returns 16 kHz the caller needs to know, and silently feeding the wrong rate to
SyncTalk would desynchronise the mouth rather than fail loudly.

Availability is a normal condition, not an error. No key, wrong provider, quota
exhausted, model withdrawn - all return None, and the caller shows the avatar as
offline instead of breaking the page.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("learnquest.tts")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# A distinct model from the chat one: the ordinary text models reject
# responseModalities: ["AUDIO"]. Overridable through the environment so a model
# rename does not need a code change - and read with os.getenv rather than added
# to config.py, which is a shared file.
#
# 3.8 Flash Lite, measured 2026-10-05 against 2.5 Flash Preview on the same key:
# a 352-char paragraph in 9.4s vs 15.5s, one sentence in ~4.5s on both. It
# answers audio/wav at 24 kHz, unwrapped by _unwrap_wav.
DEFAULT_TTS_MODEL = "gemini-3.8-flash-lite-tts"

# Tried in order when the model above is out of quota. The free tier allows
# only 10 TTS requests a day *per model*, so on a free key this chain is the
# difference between ~5 spoken replies a day and ~20. All four return 24 kHz.
DEFAULT_TTS_FALLBACK_MODELS = (
    "gemini-3.8-flash-tts,gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts"
)

# When a 429 carries no retryDelay, how long to leave that model alone.
DEFAULT_EXHAUSTED_SECONDS = 3600.0

# model -> time.monotonic() before which it is known to be out of quota
_exhausted_until: dict[str, float] = {}

# Gemini's prebuilt voices. The avatar is a man (Alapon, trained on Redwan), so
# the voice is male: Charon, Gemini's "informative" voice. The live tutor uses
# the same voice, so all three tabs sound like one person.
DEFAULT_VOICE = "Charon"

# TTS is billed per call and slower than text. Redwan's lines are short by design
# (the tutor prompt caps replies at ~120 words); anything longer is refused
# rather than silently truncated mid-sentence.
MAX_TTS_CHARS = 1200

REQUEST_TIMEOUT_SECONDS = 45.0

# Redwan repeats himself more than you would think - fallback openings, push-back
# lines, replayed messages. A small cache keeps a re-listen instant and unbilled.
_CACHE_MAX_ENTRIES = 32
_cache: OrderedDict[tuple[str, str], "Speech"] = OrderedDict()
_cache_lock = asyncio.Lock()


@dataclass(frozen=True)
class Speech:
    """Raw mono PCM plus the rate it must be played at."""

    pcm: bytes
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return len(self.pcm) / 2 / self.sample_rate if self.sample_rate else 0.0


def tts_model() -> str:
    return os.getenv("TTS_MODEL", DEFAULT_TTS_MODEL)


def tts_models() -> list[str]:
    """The configured model, then `TTS_FALLBACK_MODELS`, without repeats."""
    fallbacks = os.getenv("TTS_FALLBACK_MODELS", DEFAULT_TTS_FALLBACK_MODELS)
    models = [tts_model(), *(m.strip() for m in fallbacks.split(","))]
    return list(dict.fromkeys(m for m in models if m))


def _retry_delay(response) -> float:  # noqa: ANN001
    """Seconds until a 429'd model has quota again, from the error details."""
    try:
        for detail in response.json()["error"].get("details", []):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_EXHAUSTED_SECONDS


def tts_voice() -> str:
    return os.getenv("TTS_VOICE", DEFAULT_VOICE)


def is_available() -> bool:
    """Whether a synthesis attempt could possibly succeed.

    Cheap and synchronous so `/api/avatar/status` can answer without paying for
    a round trip. It cannot know about quota - that surfaces as a None later.
    """
    return settings.llm_provider.lower() == "gemini" and bool(settings.llm_api_key)


def _parse_sample_rate(mime_type: str) -> int | None:
    """Pull the rate out of `audio/L16;codec=pcm;rate=24000`."""
    match = re.search(r"rate=(\d+)", mime_type or "")
    return int(match.group(1)) if match else None


def _unwrap_wav(data: bytes) -> tuple[bytes, int] | None:
    """PCM and rate from a WAV file, or None if it is not 16-bit mono PCM.

    The 3.x TTS models answer `audio/wav` instead of bare L16. The rate is not
    in that MIME type but it is in the file's own header, so reading it there
    is still not a guess. Anything other than 16-bit mono PCM is refused: the
    avatar's audio path assumes exactly that.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos, fmt = 12, None
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        body = data[pos + 8 : pos + 8 + size]
        if chunk_id == b"fmt " and len(body) >= 16:
            fmt = (
                int.from_bytes(body[0:2], "little"),  # 1 = PCM
                int.from_bytes(body[2:4], "little"),  # channels
                int.from_bytes(body[4:8], "little"),  # sample rate
                int.from_bytes(body[14:16], "little"),  # bits per sample
            )
        elif chunk_id == b"data" and fmt is not None:
            audio_format, channels, rate, bits = fmt
            if audio_format != 1 or channels != 1 or bits != 16:
                return None
            # Streamed WAVs may declare a placeholder size; take what is there.
            return data[pos + 8 : pos + 8 + min(size, len(data) - pos - 8)], rate
        pos += 8 + size + (size & 1)
    return None


async def synthesize(text: str, *, voice: str | None = None) -> Speech | None:
    """Speak `text`. Returns None whenever speech is not available.

    Never raises: a tutor that cannot find its voice should fall silent, not
    take the request down with it.
    """
    clean = (text or "").strip()
    if not clean:
        return None

    if not is_available():
        logger.debug("TTS unavailable: provider=%s", settings.llm_provider)
        return None

    if len(clean) > MAX_TTS_CHARS:
        logger.info("Refusing to synthesize %d chars (max %d)", len(clean), MAX_TTS_CHARS)
        return None

    chosen_voice = voice or tts_voice()
    key = (clean, chosen_voice)

    async with _cache_lock:
        cached = _cache.get(key)
        if cached is not None:
            _cache.move_to_end(key)
            return cached

    from app.services.llm_client import get_http_client

    body = {
        "contents": [{"parts": [{"text": clean}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": chosen_voice}}
            },
        },
    }

    response = None
    for model in tts_models():
        if _exhausted_until.get(model, 0.0) > time.monotonic():
            continue
        try:
            response = await get_http_client().post(
                f"{GEMINI_BASE}/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": settings.llm_api_key,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TTS request failed on %s: %s", model, exc)
            response = None
            continue
        if response.status_code == 200:
            break
        # 429 is the free-tier quota (10 requests a day per model), an
        # expected daily event: park that model until it resets and move on.
        # 400 happens when a model decides a very short line is a prompt to
        # answer rather than text to read; another model usually reads it.
        if response.status_code == 429:
            _exhausted_until[model] = time.monotonic() + _retry_delay(response)
        logger.warning(
            "TTS %s returned %s: %s", model, response.status_code, response.text[:200]
        )
        response = None

    if response is None:
        return None

    try:
        payload = response.json()
        inline = payload["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(inline["data"])
        mime_type = inline.get("mimeType", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("TTS response was not audio: %s", exc)
        return None

    sample_rate = _parse_sample_rate(mime_type)
    if sample_rate is None and "wav" in mime_type.lower():
        unwrapped = _unwrap_wav(pcm)
        if unwrapped is not None:
            pcm, sample_rate = unwrapped
    if sample_rate is None:
        logger.warning("TTS gave no sample rate in %r; refusing to guess", mime_type)
        return None
    if not pcm:
        return None

    speech = Speech(pcm=pcm, sample_rate=sample_rate)
    logger.info(
        "Synthesized %.2fs at %d Hz for %d chars",
        speech.duration_seconds,
        sample_rate,
        len(clean),
    )

    async with _cache_lock:
        _cache[key] = speech
        while len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)

    return speech


def clear_cache() -> None:
    """Drop cached audio and quota state. Used by tests."""
    _cache.clear()
    _exhausted_until.clear()

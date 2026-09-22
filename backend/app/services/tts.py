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
from collections import OrderedDict
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("learnquest.tts")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# A distinct model from the chat one: the ordinary text models reject
# responseModalities: ["AUDIO"]. Overridable through the environment so a model
# rename does not need a code change - and read with os.getenv rather than added
# to config.py, which is a shared file.
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"

# Gemini's prebuilt voices. Kore is even and unhurried, which suits a tutor.
DEFAULT_VOICE = "Kore"

# TTS is billed per call and slower than text. Nova's lines are short by design
# (the tutor prompt caps replies at ~120 words); anything longer is refused
# rather than silently truncated mid-sentence.
MAX_TTS_CHARS = 1200

REQUEST_TIMEOUT_SECONDS = 45.0

# Nova repeats herself more than you would think - fallback openings, push-back
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

    try:
        response = await get_http_client().post(
            f"{GEMINI_BASE}/models/{tts_model()}:generateContent",
            headers={
                "x-goog-api-key": settings.llm_api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("TTS request failed: %s", exc)
        return None

    if response.status_code != 200:
        # 429 here is the free-tier quota, which is an expected daily event
        # rather than a fault - log it plainly and let the avatar go quiet.
        logger.warning(
            "TTS returned %s: %s", response.status_code, response.text[:200]
        )
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
    """Drop cached audio. Used by tests."""
    _cache.clear()

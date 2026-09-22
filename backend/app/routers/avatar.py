"""Avatar speech and lipsync payloads.

OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
See plan.md §6.6.

The avatar is SyncTalk streaming real video of a trained face. It needs two
things to work: the GPU service reachable at `AVATAR_SERVICE_URL`, and a speech
provider, because the service renders frames only in response to audio. Either
one missing means the avatar is offline, and `/status` says which.

Why session setup is proxied
----------------------------
The SyncTalk service (`avatar-service/avatar_server_ws.py`) registers no CORS
middleware, so a browser cannot call its `/health` or `/session` endpoints
directly - the preflight fails. WebSocket handshakes are not subject to CORS, so
the frontend opens `/ws/video/{sid}` itself and only the HTTP setup comes
through here. That also keeps the GPU box's address out of the client bundle
until a signed-in user actually asks for a session.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.config import settings
from app.deps import CurrentUser
from app.services.tts import is_available as tts_is_available
from app.services.tts import synthesize

logger = logging.getLogger("learnquest.avatar")

router = APIRouter(prefix="/api/avatar", tags=["avatar"])

# The stream is 25 fps and the PCM that arrives with each segment is 24 kHz
# signed 16-bit mono. Both are fixed by the service (see its module docstring)
# and the client needs them to schedule playback, so they are published here
# rather than hard-coded a second time in the frontend.
STREAM_FPS = 25
STREAM_SAMPLE_RATE = 24000

# A dead GPU box must not hang the tutor page. Short enough that the offline
# panel appears immediately instead of the page hanging on a probe.
PROBE_TIMEOUT_SECONDS = 2.5
SESSION_TIMEOUT_SECONDS = 5.0


class SpeakRequest(BaseModel):
    text: str
    expression: str | None = "neutral"


def _ws_base(http_url: str) -> str:
    """http://host -> ws://host, https://host -> wss://host."""
    url = http_url.rstrip("/")
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


async def _probe_service() -> dict[str, Any] | None:
    """Ask the avatar service whether it is actually up. None if it is not."""
    if not settings.avatar_service_url:
        return None

    from app.services.llm_client import get_http_client

    try:
        response = await get_http_client().get(
            f"{settings.avatar_service_url.rstrip('/')}/health",
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001 - unreachable is a normal state here
        logger.info("Avatar service probe failed (reporting offline): %s", exc)
        return None


@router.get("/status")
async def avatar_status() -> dict[str, Any]:
    """Whether the avatar can render AND speak, with a reason when it cannot.

    Both halves are required: the GPU service only produces frames in response
    to audio, so a reachable box with no speech provider is a frozen face. The
    frontend shows an offline panel carrying `reason` rather than a black square.
    """
    speech_ready = tts_is_available()

    if not settings.avatar_service_url:
        return {
            "online": False,
            "speech": speech_ready,
            "reason": "AVATAR_SERVICE_URL is not set",
        }

    health = await _probe_service()
    if health is None:
        return {
            "online": False,
            "speech": speech_ready,
            "reason": "Avatar service is not reachable",
        }
    if not health.get("models_loaded", True):
        return {
            "online": False,
            "speech": speech_ready,
            "reason": "Avatar service is still loading",
        }
    if not speech_ready:
        # The service renders only when audio arrives. Reporting "online" with
        # no voice would give the student a permanently frozen face and no
        # explanation, so this counts as offline with a reason.
        return {
            "online": False,
            "speech": False,
            "reason": "No speech provider configured (set LLM_PROVIDER=gemini)",
        }

    return {
        "online": True,
        "speech": True,
        "fps": STREAM_FPS,
        "sample_rate": STREAM_SAMPLE_RATE,
        "device": health.get("device"),
        "image_size": health.get("image_size"),
    }


@router.post("/session", status_code=status.HTTP_201_CREATED)
async def create_avatar_session(user: CurrentUser) -> dict[str, Any]:
    """Open a SyncTalk session and hand the browser its WebSocket URLs.

    Returns 503 when the service is unset or down, which the frontend shows as
    an offline panel rather than as an error.
    """
    if not settings.avatar_service_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Avatar service is not configured.",
        )

    from app.services.llm_client import get_http_client

    base = settings.avatar_service_url.rstrip("/")
    try:
        response = await get_http_client().post(
            f"{base}/session", timeout=SESSION_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not open an avatar session: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Avatar service is not reachable.",
        ) from exc

    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Avatar service returned no session id.",
        )

    ws_base = _ws_base(base)
    return {
        "session_id": session_id,
        "video_ws_url": f"{ws_base}/ws/video/{session_id}",
        "audio_ws_url": f"{ws_base}/ws/audio/{session_id}",
        "idle_cache_ready": bool(data.get("idle_cache_ready")),
        "fps": STREAM_FPS,
        "sample_rate": STREAM_SAMPLE_RATE,
    }


@router.get("/config")
def avatar_config() -> dict[str, Any]:
    """Expression states and stream parameters the frontend should support."""
    return {
        "expressions": ["neutral", "thinking", "explaining", "encouraging"],
        "stream": {"fps": STREAM_FPS, "sample_rate": STREAM_SAMPLE_RATE},
        "speech": {"available": tts_is_available()},
    }


@router.post("/speech")
async def synthesize_speech(body: SpeakRequest, user: CurrentUser) -> Response:
    """Synthesize `text` and return raw PCM for the client to feed SyncTalk.

    Returns the bytes themselves rather than JSON: a few seconds of 24 kHz PCM
    is ~200 KB, and base64 inside a JSON envelope would inflate that by a third
    for no benefit. The sample rate travels in the Content-Type, exactly as the
    provider sends it, and in an explicit header so the browser does not have to
    parse a MIME string.

    503 means "no voice available" - a normal condition the client handles by
    showing the avatar as offline, not an error worth surfacing to the student.
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to speak."
        )

    speech = await synthesize(text)
    if speech is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech synthesis is unavailable.",
        )

    # The client forwards these bytes straight to SyncTalk, which works in
    # STREAM_SAMPLE_RATE. Resampling would need numpy, which the backend does
    # not carry, and feeding a mismatched rate would desynchronise the mouth
    # silently - so refuse loudly instead. Gemini returns 24 kHz today, which
    # is exactly the rate the service wants.
    if speech.sample_rate != STREAM_SAMPLE_RATE:
        logger.error(
            "TTS returned %d Hz but the avatar needs %d Hz",
            speech.sample_rate,
            STREAM_SAMPLE_RATE,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech provider returned an unusable sample rate.",
        )

    return Response(
        content=speech.pcm,
        media_type=f"audio/L16;codec=pcm;rate={speech.sample_rate}",
        headers={
            "X-Sample-Rate": str(speech.sample_rate),
            "X-Duration-Ms": str(int(speech.duration_seconds * 1000)),
            "Cache-Control": "no-store",
        },
    )

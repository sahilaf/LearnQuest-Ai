"""Avatar speech and lipsync payloads.

OWNER: Member 1. See plan.md 6.6.

These are stubs so the router graph is wired from day 1. Replace the bodies with
real implementations - keep the paths, they are the contract other members code against.
"""

from fastapi import APIRouter

from app.deps import CurrentUser

router = APIRouter(prefix="/api/avatar", tags=["avatar"])


from app.config import settings


@router.get("/status")
def avatar_status() -> dict:
    """Which tier is live. The frontend uses this to pick its renderer.

    Tier A = browser TTS + viseme lipsync (always available).
    Tier B = SyncTalk on a GPU box (only when AVATAR_SERVICE_URL is set).
    """
    return {
        "tier": "B" if settings.avatar_service_url else "A",
        "service_url": settings.avatar_service_url or None,
    }


@router.get("/config")
def avatar_config() -> dict:
    """Expression states and viseme set the frontend should support."""
    return {
        "expressions": ["neutral", "thinking", "explaining", "encouraging"],
        "visemes": ["sil", "AA", "E", "I", "O", "U", "M", "F", "L", "S"],
        "idle": {"blink_interval_ms": [3000, 6000], "sway": True},
    }


@router.post("/speak")
async def speak(user: CurrentUser, payload: dict) -> dict:
    """Turn text into audio plus a viseme timeline.

    Body: {text, expression?}
    Returns: {audio_url, visemes, video_stream_url?}

    video_stream_url is present only on Tier B. The frontend falls back to Tier A
    when it is absent - same endpoint, graceful degradation (plan.md 6.6).
    """
    # TODO(M1): services.tts.synthesize() -> audio + visemes.
    return {"audio_url": None, "visemes": [], "video_stream_url": None}

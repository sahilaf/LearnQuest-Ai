"""Text to speech and viseme extraction. OWNER: Member 1. See plan.md 6.6.

Tier A: the browser does the speaking via the Web Speech API and this module only
produces the viseme timeline. Tier B: synthesize server-side and hand the wav to
the SyncTalk service.

Viseme payload contract (also stored in messages.visemes):
    [{"t": 0.00, "v": "sil"}, {"t": 0.08, "v": "AA"}, {"t": 0.19, "v": "M"}]
"""

VISEMES = ["sil", "AA", "E", "I", "O", "U", "M", "F", "L", "S"]


def text_to_visemes(text: str, duration_seconds: float | None = None) -> list[dict]:
    """Map text to a viseme timeline the frontend can play against the audio."""
    raise NotImplementedError("TODO(M1): week 1 spike, week 3 accurate")


async def synthesize(text: str) -> dict:
    """Return {audio_url, visemes} - or {audio_url: None} for browser-side TTS."""
    raise NotImplementedError("TODO(M1): week 2")

"""Local text-to-speech for LearnQuest: Kokoro-82M on the CPU. OWNER: Member 1.

Why this exists
---------------
Gemini TTS on a free key allows ~10 requests a day per model, which a single
afternoon of testing used up - and then Redwan could not read a lesson or a
reply aloud. Kokoro is an open-weight (Apache-2.0) 82M-parameter TTS model
that runs here, free and without limits.

It outputs 24 kHz mono - exactly the rate the SyncTalk avatar consumes - so
its audio goes to the face unchanged, like Gemini's.

The ONNX build is used: onnxruntime and numpy only, no PyTorch, so it runs
next to the backend on any machine, with or without the GPU avatar.

API (bound to 127.0.0.1; only the backend calls it)
---------------------------------------------------
  GET  /health -> {"ok": true, "voice": "...", "sample_rate": 24000, "voices": [...]}
  POST /speak  {"text": "...", "voice": optional, "speed": optional}
       -> raw signed 16-bit little-endian mono PCM, rate in X-Sample-Rate

Run:  .venv\\Scripts\\python server.py      (port 5002, or TTS_SERVICE_PORT)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
MODEL_PATH = Path(os.getenv("KOKORO_MODEL", HERE / "models" / "kokoro-v1.0.onnx"))
VOICES_PATH = Path(os.getenv("KOKORO_VOICES", HERE / "models" / "voices-v1.0.bin"))
# A male American voice, to match the avatar (Redwan). Others: am_adam,
# am_fenrir, am_puck, bm_george (British) - see GET /health for the list.
DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "am_michael")
MAX_CHARS = 1200  # the backend never sends more; the same cap as Gemini

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger("tts-service")

app = FastAPI(title="LearnQuest local TTS (Kokoro)")
_kokoro = None
# One ONNX session; synthesis is serialized rather than run concurrently.
_lock = threading.Lock()


def _engine():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        if not MODEL_PATH.exists() or not VOICES_PATH.exists():
            raise RuntimeError(f"Model files missing: {MODEL_PATH.name}, {VOICES_PATH.name} (see README.md)")
        started = time.perf_counter()
        _kokoro = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
        logger.info("Kokoro loaded in %.1fs", time.perf_counter() - started)
    return _kokoro


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@app.on_event("startup")
def _load() -> None:
    try:
        _engine()
    except Exception as exc:  # noqa: BLE001 - /health reports it
        logger.error("Kokoro failed to load: %s", exc)


@app.get("/health")
def health() -> dict:
    try:
        engine = _engine()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"ok": True, "voice": DEFAULT_VOICE, "sample_rate": 24000, "voices": engine.get_voices()}


@app.post("/speak")
def speak(body: SpeakRequest) -> Response:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to speak.")
    try:
        engine = _engine()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    voice = body.voice or DEFAULT_VOICE
    if voice not in engine.get_voices():
        raise HTTPException(status_code=400, detail=f"Unknown voice {voice!r}.")

    started = time.perf_counter()
    with _lock:
        samples, rate = engine.create(text, voice=voice, speed=body.speed, lang="en-us")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    seconds = len(pcm) / 2 / rate
    logger.info("%d chars -> %.1fs of audio in %.1fs", len(text), seconds, time.perf_counter() - started)
    return Response(
        content=pcm,
        media_type=f"audio/L16;codec=pcm;rate={rate}",
        headers={"X-Sample-Rate": str(rate), "X-Duration-Ms": str(int(seconds * 1000))},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("TTS_SERVICE_PORT", "5002")))

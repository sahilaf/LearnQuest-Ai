"""Live voice conversation with the tutor. OWNER: Member 1.

One WebSocket per conversation, bridged to Gemini Live:

    browser mic (16 kHz PCM) -> here -> Gemini Live -> here -> browser (24 kHz PCM)

The browser plays the reply itself, or hands it to the avatar service when the
student has connected the avatar - this endpoint does not know or care which.

Protocol
--------
Client -> server
  text   {"type": "start", "token": <Supabase JWT or null>, "conversation": <number>,
          "reading": <optional: the lesson passage the student paused on>}
         must be the first message; browsers cannot set headers on a WebSocket,
         and a token in the URL would be written to access logs
  binary 16-bit mono PCM at 16 kHz from the microphone
  text   {"type": "text", "text": "..."}   a typed message mid-call
  text   {"type": "end"}

Server -> client
  text   {"type": "ready", "conversation": n, "output_rate": 24000}
  binary 16-bit mono PCM at 24 kHz, the tutor's voice
  text   {"type": "transcript", "role": "user" | "tutor", "text": <delta>}
  text   {"type": "interrupted"}    the student talked over the tutor
  text   {"type": "turn_complete"}
  text   {"type": "error", "message": "..."} then close
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.deps import get_current_user
from app.services import live_tutor
from app.services.tts import tts_voice

logger = logging.getLogger("learnquest.live")

router = APIRouter(prefix="/api/live", tags=["live"])

INPUT_RATE = 16000
OUTPUT_RATE = 24000
START_TIMEOUT_SECONDS = 10.0

# Limits. Every live second is a paid/quota'd Gemini stream, so one student
# cannot hold several calls open (two tabs, a stuck page) or one forever.
MAX_CALLS_PER_USER = 1
MAX_CALL_SECONDS = 15 * 60

# user id -> live calls open right now (one process; fine for this deployment).
_open_calls: dict[str, int] = {}


def _live_config(instruction: str) -> Any:
    from google.genai import types

    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=instruction,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=tts_voice())
            ),
            language_code="en-US",
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # Long calls would otherwise hit the context limit and drop.
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )


async def _fail(ws: WebSocket, message: str, code: int = 1011) -> None:
    try:
        await ws.send_text(json.dumps({"type": "error", "message": message}))
        await ws.close(code=code)
    except Exception:  # noqa: BLE001 - the socket may already be gone
        pass


@router.websocket("/ws")
async def live_conversation(ws: WebSocket) -> None:
    await ws.accept()

    # 1. Who is this, and which conversation are they continuing?
    try:
        start = json.loads(await asyncio.wait_for(ws.receive_text(), START_TIMEOUT_SECONDS))
        if start.get("type") != "start":
            raise ValueError("first message must be start")
    except Exception:  # noqa: BLE001
        await _fail(ws, "Expected a start message.", 4400)
        return

    token = start.get("token")
    try:
        user = await run_in_threadpool(get_current_user, f"Bearer {token}" if token else None)
    except Exception:  # noqa: BLE001
        await _fail(ws, "Not signed in.", 4401)
        return
    user_id = uuid.UUID(user["id"])

    if _open_calls.get(user["id"], 0) >= MAX_CALLS_PER_USER:
        await _fail(ws, "You already have a live call open. End it first.", 4429)
        return
    _open_calls[user["id"]] = _open_calls.get(user["id"], 0) + 1
    try:
        await _run_call(ws, start, user_id)
    finally:
        _open_calls[user["id"]] -= 1
        if _open_calls[user["id"]] <= 0:
            _open_calls.pop(user["id"], None)


async def _run_call(ws: WebSocket, start: dict, user_id: uuid.UUID) -> None:
    conversation_id, number = await run_in_threadpool(
        live_tutor.resolve_conversation_id, user_id, start.get("conversation")
    )

    from app.services import e2e_fakes

    fake = e2e_fakes.e2e_enabled()
    if not settings.llm_api_key and not fake:
        await _fail(ws, "No Gemini key configured, so live voice is unavailable.")
        return

    # 2. The tutor's whole context, as one instruction.
    instruction = await run_in_threadpool(
        live_tutor.build_live_instruction, user_id, conversation_id, start.get("reading")
    )

    from google import genai
    from google.genai import types

    # End-to-end tests talk to a scripted session instead of Gemini Live.
    client = e2e_fakes.FakeLiveClient() if fake else genai.Client(api_key=settings.llm_api_key)
    try:
        async with client.aio.live.connect(
            model=live_tutor.live_model(), config=_live_config(instruction)
        ) as session:
            await ws.send_text(
                json.dumps({"type": "ready", "conversation": number, "output_rate": OUTPUT_RATE})
            )
            logger.info("Live session started for user=%s conversation=%s", user_id, number)
            try:
                await asyncio.wait_for(
                    _bridge(ws, session, types, conversation_id), MAX_CALL_SECONDS
                )
            except asyncio.TimeoutError:
                await _fail(ws, "Calls are limited to 15 minutes. Start a new one to keep going.", 1000)
                return
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("Live session failed: %s", exc)
        await _fail(ws, "The live tutor is unavailable right now. Try again, or use Chat.")
        return
    try:
        await ws.close()
    except Exception:  # noqa: BLE001
        pass


async def _bridge(ws: WebSocket, session: Any, types: Any, conversation_id: uuid.UUID | None) -> None:
    """Pump both directions until either side hangs up."""
    user_said: list[str] = []
    tutor_said: list[str] = []

    async def from_browser() -> None:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            data = msg.get("bytes")
            if data:
                await session.send_realtime_input(
                    audio=types.Blob(data=data, mime_type=f"audio/pcm;rate={INPUT_RATE}")
                )
                continue
            text = msg.get("text")
            if not text:
                continue
            try:
                event = json.loads(text)
            except ValueError:
                continue
            if event.get("type") == "end":
                return
            if event.get("type") == "text" and str(event.get("text", "")).strip():
                typed = str(event["text"]).strip()
                user_said.append(typed)
                await session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=typed)]),
                    turn_complete=True,
                )

    async def from_gemini() -> None:
        # receive() yields one model turn and then stops, so loop over turns.
        while True:
            async for message in session.receive():
                if message.data:
                    await ws.send_bytes(message.data)
                content = message.server_content
                if message.go_away is not None:
                    await ws.send_text(json.dumps(
                        {"type": "error", "message": "The live session reached its time limit."}))
                    return
                if content is None:
                    continue
                if content.input_transcription and content.input_transcription.text:
                    user_said.append(content.input_transcription.text)
                    await ws.send_text(json.dumps(
                        {"type": "transcript", "role": "user", "text": content.input_transcription.text}))
                if content.output_transcription and content.output_transcription.text:
                    tutor_said.append(content.output_transcription.text)
                    await ws.send_text(json.dumps(
                        {"type": "transcript", "role": "tutor", "text": content.output_transcription.text}))
                if content.interrupted:
                    await ws.send_text(json.dumps({"type": "interrupted"}))
                if content.turn_complete:
                    await ws.send_text(json.dumps({"type": "turn_complete"}))
                    heard, said = "".join(user_said), "".join(tutor_said)
                    user_said.clear()
                    tutor_said.clear()
                    await run_in_threadpool(live_tutor.save_turn, conversation_id, heard, said)

    browser = asyncio.create_task(from_browser())
    gemini = asyncio.create_task(from_gemini())
    done, pending = await asyncio.wait({browser, gemini}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        if task.exception() and not isinstance(task.exception(), WebSocketDisconnect):
            raise task.exception()
    # Whatever was said before hanging up still belongs in the history.
    await run_in_threadpool(
        live_tutor.save_turn, conversation_id, "".join(user_said), "".join(tutor_said)
    )

"""Tests for the live tutor WebSocket (app/routers/live.py).

The bridge between the browser and Gemini Live is the part of the live tab
most likely to break quietly: a dropped transcript, an unsaved turn, a call
that never ends. Gemini is replaced by a scripted fake, so these need no
network, no key with quota, and no database.
"""

from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import live

USER = {"id": "00000000-0000-0000-0000-0000000000aa", "email": "s@learnquest.local", "role": "student"}
CONV_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _content(**kw):
    base = dict(input_transcription=None, output_transcription=None, interrupted=None, turn_complete=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _msg(data=None, **content):
    return SimpleNamespace(data=data, go_away=None, server_content=_content(**content) if content else None)


def _text(t):
    return SimpleNamespace(text=t)


class FakeSession:
    """Answers every user turn with one scripted reply."""

    def __init__(self):
        self.audio_in: list[tuple[bytes, str]] = []
        self.turns = asyncio.Queue()

    async def send_realtime_input(self, audio):
        self.audio_in.append((audio.data, audio.mime_type))

    async def send_client_content(self, turns, turn_complete):
        await self.turns.put(turns.parts[0].text)

    async def receive(self):
        # Typed turns get no input transcription from Gemini - only speech does.
        await self.turns.get()
        yield _msg(data=b"\x01\x00" * 480)
        yield _msg(output_transcription=_text("Hello "))
        yield _msg(data=b"\x02\x00" * 480, output_transcription=_text("there."))
        yield _msg(turn_complete=True)


class FakeClient:
    sessions: list[FakeSession] = []

    def __init__(self, api_key):
        self.aio = SimpleNamespace(live=SimpleNamespace(connect=self._connect))

    @asynccontextmanager
    async def _connect(self, model, config):
        session = FakeSession()
        FakeClient.sessions.append(session)
        yield session


class LiveSocketTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeClient.sessions = []
        live._open_calls.clear()
        self.saved: list[tuple] = []
        patches = [
            patch.object(settings, "llm_api_key", "test-key"),
            patch("google.genai.Client", FakeClient),
            patch.object(live, "get_current_user", lambda auth: USER),
            patch.object(live.live_tutor, "resolve_conversation_id", lambda uid, ref: (CONV_ID, 7)),
            patch.object(live.live_tutor, "build_live_instruction", lambda uid, cid, reading=None: "context"),
            patch.object(live.live_tutor, "save_turn", lambda cid, u, t: self.saved.append((cid, u, t))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(app)

    def _start(self, ws):
        ws.send_text(json.dumps({"type": "start", "token": None, "conversation": 7}))
        return json.loads(ws.receive_text())

    def _until_turn_complete(self, ws):
        audio, events = b"", []
        while True:
            msg = ws.receive()
            if msg.get("bytes"):
                audio += msg["bytes"]
                continue
            event = json.loads(msg["text"])
            events.append(event)
            if event["type"] == "turn_complete":
                return audio, events

    def test_typed_turn_round_trip_is_streamed_and_saved(self) -> None:
        with self.client.websocket_connect("/api/live/ws") as ws:
            self.assertEqual(self._start(ws), {"type": "ready", "conversation": 7, "output_rate": 24000})
            ws.send_text(json.dumps({"type": "text", "text": "What is recursion?"}))
            audio, events = self._until_turn_complete(ws)
            ws.send_text(json.dumps({"type": "end"}))

        self.assertEqual(len(audio), 2 * 960)
        tutor = "".join(e["text"] for e in events if e.get("role") == "tutor")
        self.assertEqual(tutor, "Hello there.")
        # Saved once, at turn_complete, as one exchange.
        self.assertEqual(self.saved[0], (CONV_ID, "What is recursion?", "Hello there."))

    def test_microphone_audio_reaches_gemini_at_16k(self) -> None:
        with self.client.websocket_connect("/api/live/ws") as ws:
            self._start(ws)
            ws.send_bytes(b"\x00\x01" * 1600)
            ws.send_text(json.dumps({"type": "text", "text": "hi"}))
            self._until_turn_complete(ws)
            ws.send_text(json.dumps({"type": "end"}))
        data, mime = FakeClient.sessions[0].audio_in[0]
        self.assertEqual(len(data), 3200)
        self.assertEqual(mime, "audio/pcm;rate=16000")

    def test_second_call_for_the_same_student_is_refused(self) -> None:
        with self.client.websocket_connect("/api/live/ws") as first:
            self._start(first)
            with self.client.websocket_connect("/api/live/ws") as second:
                second.send_text(json.dumps({"type": "start", "token": None}))
                event = json.loads(second.receive_text())
            self.assertEqual(event["type"], "error")
            self.assertIn("already have a live call", event["message"])
            first.send_text(json.dumps({"type": "end"}))

    def test_call_slot_is_released_after_hanging_up(self) -> None:
        for _ in range(2):
            with self.client.websocket_connect("/api/live/ws") as ws:
                self.assertEqual(self._start(ws)["type"], "ready")
                ws.send_text(json.dumps({"type": "end"}))
        self.assertEqual(live._open_calls, {})

    def test_missing_start_message_is_an_error(self) -> None:
        with self.client.websocket_connect("/api/live/ws") as ws:
            ws.send_text(json.dumps({"type": "text", "text": "hi"}))
            self.assertEqual(json.loads(ws.receive_text())["type"], "error")

    def test_not_signed_in_is_refused(self) -> None:
        def _reject(auth):
            raise HTTPException(status_code=401, detail="nope")

        with patch.object(live, "get_current_user", _reject):
            with self.client.websocket_connect("/api/live/ws") as ws:
                ws.send_text(json.dumps({"type": "start", "token": "bad"}))
                event = json.loads(ws.receive_text())
        self.assertEqual(event, {"type": "error", "message": "Not signed in."})


if __name__ == "__main__":
    unittest.main()

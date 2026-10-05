"""Scripted stand-ins for every outside AI service, for end-to-end tests.

OWNER: Member 1. Used by the Playwright suite in /e2e.

Turned on with E2E_FAKE_AI=1, and refused in production whatever the
environment says. With it on:

- the LLM is a scripted client that recognises each prompt this app sends
  (misconception, Teach-Back opening / reply / retake, grading, tutor chat)
  and answers in exactly the shape that prompt asks for;
- text-to-speech returns a short synthetic tone instead of calling Gemini;
- the live tutor talks to a scripted session instead of Gemini Live.

Why not the real models: they answer differently every run, cost quota (the
TTS free tier is 10 requests a day per model) and need a key on every test
machine. A test that fails because the model phrased something differently is
not telling you anything about your code. The real services are covered by a
separate manual smoke run - see e2e/TEST_PLAN.md.

Everything here is deterministic: the same input always gives the same output.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import struct
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from app.config import settings
from app.services.llm_client import MockLLMClient

# Text the scripted tutor and live tutor say, so tests can assert on them.
TUTOR_REPLY_PREFIX = "[e2e tutor]"
LIVE_HEARD = "Hello Redwan, can you hear me?"
LIVE_SAID = "Yes, I can hear you clearly. What would you like to learn today?"
SAMPLE_RATE = 24000


def e2e_enabled() -> bool:
    """True only when explicitly asked for, and never in production."""
    return os.getenv("E2E_FAKE_AI", "").strip() == "1" and not settings.is_production


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #

def _field(prompt: str, label: str) -> str:
    match = re.search(rf"{label}:\s*(.+)", prompt)
    return match.group(1).strip() if match else ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class ScriptedLLMClient(MockLLMClient):
    """Answers each of the app's prompts the way a sensible model would."""

    @staticmethod
    def _matches(prompt: str, given_label: str) -> bool:
        expected = _norm(_field(prompt, "Expected answer"))
        given = _norm(_field(prompt, given_label))
        return bool(expected and given) and (expected in given or given in expected)

    async def complete(self, messages: list[dict], *, temperature: float = 0.7,
                       max_tokens: int = 800, json_mode: bool = False) -> str:
        prompt = "\n".join(str(m.get("content", "")) for m in messages)

        if "Identify the single false belief" in prompt:
            answer = _field(prompt, "The student answered")[:60]
            return json.dumps({
                "misconception": f"You believe \"{answer}\" is the right answer to this kind of question.",
                "confidence": 0.9,
            })

        if "Open the conversation" in prompt:
            return json.dumps({"opening": (
                "I'm confident my answer was right - it seemed obvious to me. "
                "Can you explain why it isn't?"
            )})

        if "Decide honestly whether that explanation" in prompt:
            explanation = re.search(r'The student just told you:\s*"(.*)"', prompt, re.S)
            text = explanation.group(1) if explanation else ""
            convinced = "because" in text.lower() and len(text) >= 60
            reply = (
                "Oh, I see now - that explains where my reasoning went wrong."
                if convinced else
                "I still don't follow. You told me I'm wrong, but not why. What does my belief miss?"
            )
            return json.dumps({"reply": reply, "convinced": convinced})

        if "re-taking a question you previously got wrong" in prompt:
            if "did not explain why your belief is wrong" in prompt:
                return json.dumps({"answer": "I still believe my original answer.",
                                   "reasoning": "I was only told the answer."})
            taught = re.findall(r"the answer is ([^.\n]+)", prompt, re.I)
            answer = taught[-1].strip() if taught else "I am not sure."
            return json.dumps({"answer": answer, "reasoning": "That is what the explanation showed."})

        if "Grade one answer against the expected answer" in prompt:
            correct = self._matches(prompt, "Given answer")
            return json.dumps({"correct": correct, "score": 100 if correct else 0,
                               "why": "Matches the expected answer." if correct else "Does not match."})

        if "Grade a student's typed answer" in prompt:
            correct = self._matches(prompt, "Student's answer")
            return json.dumps({
                "verdict": "correct" if correct else "incorrect",
                "score": 1.0 if correct else 0.0,
                "confidence": 0.95,
                "feedback": "That matches the idea." if correct else "That misses the key idea.",
            })

        if "Write one question that a person holding this false belief" in prompt:
            return json.dumps({"prompt": "Which value is the correct one?", "correct_answer": "the correct one"})

        if json_mode:
            return await super().complete(messages, temperature=temperature,
                                          max_tokens=max_tokens, json_mode=True)

        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"{TUTOR_REPLY_PREFIX} You asked: \"{last[:80]}\". Let's work through it together."


# --------------------------------------------------------------------------- #
# Speech
# --------------------------------------------------------------------------- #

def tone_pcm(seconds: float, freq: float = 220.0) -> bytes:
    """Quiet 16-bit mono sine at 24 kHz - audible enough to drive a lip-sync."""
    n = int(SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)))
        for i in range(n)
    )


def fake_speech_seconds(text: str) -> float:
    """Roughly how long the line would take to say, capped for fast tests."""
    return max(0.4, min(3.0, len(text) / 60))


# --------------------------------------------------------------------------- #
# Live tutor (Gemini Live)
# --------------------------------------------------------------------------- #

# Microphone audio before the scripted student "finishes a sentence".
LIVE_TURN_BYTES = 16000 * 2 * 1  # one second at 16 kHz


def _msg(data=None, **content):
    base = dict(input_transcription=None, output_transcription=None,
                interrupted=None, turn_complete=None)
    base.update(content)
    return SimpleNamespace(data=data, go_away=None,
                           server_content=SimpleNamespace(**base) if content else None)


class FakeLiveSession:
    """Behaves like a Gemini Live session: after a second of microphone audio,
    or one typed message, it answers with audio and both transcripts."""

    def __init__(self) -> None:
        self._turns: asyncio.Queue = asyncio.Queue()
        self._mic_bytes = 0

    async def send_realtime_input(self, audio) -> None:
        self._mic_bytes += len(audio.data)
        if self._mic_bytes >= LIVE_TURN_BYTES:
            self._mic_bytes = 0
            await self._turns.put(("spoken", LIVE_HEARD))

    async def send_client_content(self, turns, turn_complete=True) -> None:
        await self._turns.put(("typed", turns.parts[0].text))

    async def receive(self):
        kind, heard = await self._turns.get()
        if kind == "spoken":
            yield _msg(input_transcription=SimpleNamespace(text=heard))
        said = LIVE_SAID if kind == "spoken" else f"{TUTOR_REPLY_PREFIX} You said: {heard}"
        words = said.split(" ")
        half = len(words) // 2
        for chunk_words, tone in ((words[:half], 0.6), (words[half:], 0.6)):
            await asyncio.sleep(0.05)
            yield _msg(data=tone_pcm(tone),
                       output_transcription=SimpleNamespace(text=" ".join(chunk_words) + " "))
        yield _msg(turn_complete=True)


class FakeLiveClient:
    """Drop-in for google.genai.Client(...) as live.py uses it."""

    def __init__(self, api_key: str = "") -> None:
        self.aio = SimpleNamespace(live=SimpleNamespace(connect=self._connect))

    @asynccontextmanager
    async def _connect(self, model: str, config: Any):
        yield FakeLiveSession()

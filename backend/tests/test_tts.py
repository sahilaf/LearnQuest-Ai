"""Tests for Member 1's speech synthesis (services/tts.py).

The avatar is audio-driven: SyncTalk renders frames only in response to audio,
so if synthesis is wrong the face does not move. These cover the parts that
would fail silently - the sample rate, the availability gate, and the refusal to
guess when the provider returns something unexpected.

No network: every test patches the HTTP client.
"""

from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from app.services import tts


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _audio_payload(pcm: bytes, mime: str = "audio/L16;codec=pcm;rate=24000") -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime,
                                "data": base64.b64encode(pcm).decode(),
                            }
                        }
                    ]
                }
            }
        ]
    }


class _FakeHTTP:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class TTSTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tts.clear_cache()
        self.gemini = patch.multiple(
            tts.settings, llm_provider="gemini", llm_api_key="test-key"
        )
        self.gemini.start()
        # Gemini only, whatever backend/.env says about the local voice.
        self.no_local = patch.dict("os.environ", {"LOCAL_TTS_URL": "", "TTS_PREFER": ""})
        self.no_local.start()

    def tearDown(self) -> None:
        self.no_local.stop()
        self.gemini.stop()
        tts.clear_cache()


class TestAvailability(TTSTestBase):
    def test_available_with_gemini_and_key(self) -> None:
        self.assertTrue(tts.is_available())

    def test_unavailable_without_a_key(self) -> None:
        with patch.object(tts.settings, "llm_api_key", ""):
            self.assertFalse(tts.is_available())

    def test_unavailable_for_another_provider(self) -> None:
        with patch.object(tts.settings, "llm_provider", "groq"):
            self.assertFalse(tts.is_available())

    def test_synthesize_short_circuits_when_unavailable(self) -> None:
        """Must not spend a call it already knows will fail."""
        http = _FakeHTTP(_Response(200, _audio_payload(b"\x00\x01")))
        with patch.object(tts.settings, "llm_provider", "mock"), patch(
            "app.services.llm_client.get_http_client", return_value=http
        ):
            self.assertIsNone(_run(tts.synthesize("hello there")))
        self.assertEqual(http.calls, [])


class TestSynthesis(TTSTestBase):
    def test_returns_pcm_and_the_declared_rate(self) -> None:
        pcm = b"\x01\x02" * 24000  # 24000 samples = 1s at 24 kHz, 16-bit mono
        http = _FakeHTTP(_Response(200, _audio_payload(pcm)))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            speech = _run(tts.synthesize("An inner join keeps matching rows."))

        self.assertIsNotNone(speech)
        self.assertEqual(speech.pcm, pcm)
        self.assertEqual(speech.sample_rate, 24000)
        self.assertAlmostEqual(speech.duration_seconds, 1.0, places=3)

    def test_reads_the_rate_rather_than_assuming_it(self) -> None:
        """A 16 kHz response must report 16 kHz, not the rate we hoped for."""
        http = _FakeHTTP(
            _Response(200, _audio_payload(b"\x00\x01" * 100, "audio/L16;codec=pcm;rate=16000"))
        )
        with patch("app.services.llm_client.get_http_client", return_value=http):
            speech = _run(tts.synthesize("hello there, this is a test"))

        self.assertEqual(speech.sample_rate, 16000)

    def test_missing_rate_is_refused(self) -> None:
        """Guessing here would desynchronise the mouth silently."""
        http = _FakeHTTP(_Response(200, _audio_payload(b"\x00\x01" * 100, "audio/L16")))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("hello there, this is a test")))

    def test_wav_response_is_unwrapped_with_the_header_rate(self) -> None:
        """The 3.x models answer audio/wav; the rate comes from the header."""
        import io
        import wave

        pcm = b"\x01\x02" * 2400
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        http = _FakeHTTP(_Response(200, _audio_payload(buf.getvalue(), "audio/wav")))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            speech = _run(tts.synthesize("hello there, this is a test"))

        self.assertEqual(speech.pcm, pcm)  # no 44-byte header played as a click
        self.assertEqual(speech.sample_rate, 24000)

    def test_stereo_wav_is_refused(self) -> None:
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x01" * 400)
        http = _FakeHTTP(_Response(200, _audio_payload(buf.getvalue(), "audio/wav")))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("hello there, this is a test")))

    def test_quota_falls_back_to_the_next_model_and_parks_the_first(self) -> None:
        """Free tier: 10 TTS requests a day per model, so one 429 is not silence."""
        quota = _Response(
            429, {"error": {"code": 429, "details": [{"retryDelay": "25193s"}]}}, "quota"
        )
        ok = _Response(200, _audio_payload(b"\x01\x02" * 2400))
        responses = iter([quota, ok, ok])

        class _Seq(_FakeHTTP):
            async def post(self, url, **kwargs):  # noqa: ANN001
                self.calls.append((url, kwargs))
                return next(responses)

        http = _Seq(None)
        with patch.dict("os.environ", {"TTS_MODEL": "a-tts", "TTS_FALLBACK_MODELS": "b-tts"}), patch(
            "app.services.llm_client.get_http_client", return_value=http
        ):
            self.assertIsNotNone(_run(tts.synthesize("first line to speak")))
            self.assertIsNotNone(_run(tts.synthesize("second line to speak")))

        models = [url.split("/models/")[1].split(":")[0] for url, _ in http.calls]
        # The exhausted model is not asked again until its retryDelay passes.
        self.assertEqual(models, ["a-tts", "b-tts", "b-tts"])

    def test_quota_error_returns_none(self) -> None:
        http = _FakeHTTP(_Response(429, {}, "quota exceeded"))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("hello there, this is a test")))

    def test_transport_failure_returns_none(self) -> None:
        http = _FakeHTTP(RuntimeError("connection reset"))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("hello there, this is a test")))

    def test_non_audio_response_returns_none(self) -> None:
        http = _FakeHTTP(_Response(200, {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("hello there, this is a test")))

    def test_empty_text_makes_no_call(self) -> None:
        http = _FakeHTTP(_Response(200, _audio_payload(b"\x00\x01")))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("   ")))
        self.assertEqual(http.calls, [])

    def test_overlong_text_is_refused_not_truncated(self) -> None:
        http = _FakeHTTP(_Response(200, _audio_payload(b"\x00\x01")))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            self.assertIsNone(_run(tts.synthesize("x" * (tts.MAX_TTS_CHARS + 1))))
        self.assertEqual(http.calls, [])


class TestCache(TTSTestBase):
    def test_repeated_line_is_not_billed_twice(self) -> None:
        pcm = b"\x01\x02" * 2400
        http = _FakeHTTP(_Response(200, _audio_payload(pcm)))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            first = _run(tts.synthesize("Redwan says this twice."))
            second = _run(tts.synthesize("Redwan says this twice."))

        self.assertEqual(len(http.calls), 1)
        self.assertEqual(first.pcm, second.pcm)

    def test_cache_is_bounded(self) -> None:
        http = _FakeHTTP(_Response(200, _audio_payload(b"\x01\x02" * 10)))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            for i in range(tts._CACHE_MAX_ENTRIES + 5):
                _run(tts.synthesize(f"line number {i} for the tutor"))

        self.assertLessEqual(len(tts._cache), tts._CACHE_MAX_ENTRIES)


class TestSpeechEndpoint(TTSTestBase):
    """The endpoint must not hand the client a rate SyncTalk cannot use."""

    def _client(self):
        from fastapi.testclient import TestClient

        from app.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "id": "00000000-0000-0000-0000-000000000001",
            "email": "t@local",
            "role": "student",
        }
        self.addCleanup(app.dependency_overrides.clear)
        return TestClient(app)

    def test_returns_raw_pcm_with_the_rate_in_the_headers(self) -> None:
        pcm = b"\x01\x02" * 24000
        speech = tts.Speech(pcm=pcm, sample_rate=24000)

        async def _fake(text, **kwargs):  # noqa: ANN001
            return speech

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, pcm)
        self.assertEqual(response.headers["X-Sample-Rate"], "24000")
        self.assertIn("rate=24000", response.headers["content-type"])

    def test_only_lesson_narration_is_kept_on_disk(self) -> None:
        seen: list[bool] = []

        async def _fake(text, persist=False, **kwargs):  # noqa: ANN001
            seen.append(persist)
            return tts.Speech(pcm=b"\x01\x02" * 10, sample_rate=24000)

        with patch("app.routers.avatar.synthesize", _fake):
            client = self._client()
            client.post("/api/avatar/speech", json={"text": "a chat reply"})
            client.post("/api/avatar/speech", json={"text": "a lesson line", "purpose": "lesson"})

        self.assertEqual(seen, [False, True])

    def test_mismatched_rate_is_refused_rather_than_shipped(self) -> None:
        async def _fake(text, **kwargs):  # noqa: ANN001
            return tts.Speech(pcm=b"\x00\x01" * 100, sample_rate=16000)

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 503)

    def test_no_voice_is_a_503(self) -> None:
        async def _fake(text, **kwargs):  # noqa: ANN001
            return None

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 503)

    def test_empty_text_is_a_400(self) -> None:
        response = self._client().post("/api/avatar/speech", json={"text": "   "})
        self.assertEqual(response.status_code, 400)


class _ServiceResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        if isinstance(self._payload, Exception):
            raise self._payload

    def json(self):
        return self._payload


class _FakeAvatarService:
    """Stands in for the GPU box: /session, and /idle/info when it has one."""

    def __init__(self, idle_info):
        self.idle_info = idle_info

    async def post(self, url, **_kwargs):  # noqa: ANN001
        assert url.endswith("/session")
        return _ServiceResponse({"session_id": "abc123", "idle_cache_ready": True})

    async def get(self, url, **_kwargs):  # noqa: ANN001
        assert url.endswith("/idle/info")
        return _ServiceResponse(self.idle_info)


class TestAvatarSessionIdle(TTSTestBase):
    """The session hands the browser the idle loop it plays between replies.

    Without it the face is blank before the first reply and frozen mid-word
    after every one, so this is part of the avatar working, not decoration.
    """

    _client = TestSpeechEndpoint._client

    def _session(self, idle_info):
        from app.config import settings

        with patch.object(settings, "avatar_service_url", "http://gpu:5001"), patch(
            "app.services.llm_client.get_http_client",
            lambda: _FakeAvatarService(idle_info),
        ):
            return self._client().post("/api/avatar/session")

    def test_session_carries_the_idle_loop(self) -> None:
        response = self._session(
            {"ready": True, "frame_count": 3, "source_map": [7639, 7640, 7641, 7642]}
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["video_ws_url"], "ws://gpu:5001/ws/video/abc123")
        idle = body["idle"]
        self.assertEqual(idle["frame_count"], 3)
        # Trimmed to the frames that exist, so no position maps past the clip.
        self.assertEqual(idle["source_map"], [7639, 7640, 7641])
        self.assertEqual(
            idle["frame_url"].format(index=2), "http://gpu:5001/idle/frame/2"
        )

    def test_unreadable_idle_cache_still_opens_a_session(self) -> None:
        response = self._session(RuntimeError("idle cache broke"))

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["idle"])

    def test_idle_cache_not_ready_is_none(self) -> None:
        response = self._session({"ready": False, "frame_count": 0})

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["idle"])


if __name__ == "__main__":
    unittest.main()


class TestLessonDiskCache(TTSTestBase):
    """Lesson narration is paid for once, then read from disk."""

    def setUp(self) -> None:
        super().setUp()
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict("os.environ", {"TTS_CACHE_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()
        super().tearDown()

    def test_lesson_audio_survives_a_restart_without_a_second_call(self) -> None:
        pcm = b"\x01\x02" * 2400
        http = _FakeHTTP(_Response(200, _audio_payload(pcm)))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            first = _run(tts.synthesize("A primary key identifies a row.", persist=True))
            tts.clear_cache()  # what a backend restart does to the memory cache
            again = _run(tts.synthesize("A primary key identifies a row.", persist=True))

        self.assertEqual(len(http.calls), 1)
        self.assertEqual((again.pcm, again.sample_rate), (first.pcm, 24000))

    def test_chat_replies_are_not_written_to_disk(self) -> None:
        import os

        http = _FakeHTTP(_Response(200, _audio_payload(b"\x01\x02" * 100)))
        with patch("app.services.llm_client.get_http_client", return_value=http):
            _run(tts.synthesize("Just a chat reply."))
        self.assertEqual(os.listdir(self.tmp.name), [])


class _LocalResponse:
    def __init__(self, status_code=200, content=b"", rate="24000"):
        self.status_code = status_code
        self.content = content
        self.headers = {"X-Sample-Rate": rate} if rate else {}
        self.text = ""


class _Router:
    """Answers the local Kokoro service and Gemini differently, and records both."""

    def __init__(self, local, gemini):
        self.local, self.gemini, self.calls = local, gemini, []

    async def post(self, url, **kwargs):
        local = url.endswith("/speak")
        self.calls.append("local" if local else "gemini")
        answer = self.local if local else self.gemini
        if isinstance(answer, Exception):
            raise answer
        return answer


class TestLocalVoice(TTSTestBase):
    """The free local Kokoro voice goes first; Gemini is the fallback."""

    def setUp(self) -> None:
        super().setUp()
        self.local_on = patch.dict("os.environ", {"LOCAL_TTS_URL": "http://127.0.0.1:5002"})
        self.local_on.start()

    def tearDown(self) -> None:
        self.local_on.stop()
        super().tearDown()

    def test_local_voice_is_used_first_and_gemini_is_not_billed(self) -> None:
        router = _Router(_LocalResponse(content=b"" * 2400), _Response(200, _audio_payload(b"		")))
        with patch("app.services.llm_client.get_http_client", return_value=router):
            speech = _run(tts.synthesize("A primary key identifies a row."))
        self.assertEqual(router.calls, ["local"])
        self.assertEqual((speech.pcm, speech.sample_rate), (b"" * 2400, 24000))

    def test_falls_back_to_gemini_when_the_local_voice_is_down(self) -> None:
        router = _Router(ConnectionError("refused"), _Response(200, _audio_payload(b"		" * 10)))
        with patch("app.services.llm_client.get_http_client", return_value=router):
            first = _run(tts.synthesize("First line."))
            _run(tts.synthesize("Second line."))
        self.assertEqual(first.pcm, b"		" * 10)
        # Down is remembered: the second line does not wait on a dead port again.
        self.assertEqual(router.calls, ["local", "gemini", "gemini"])

    def test_a_local_answer_without_a_rate_is_refused(self) -> None:
        router = _Router(_LocalResponse(content=b"", rate=""), _Response(429, {}, "quota"))
        with patch("app.services.llm_client.get_http_client", return_value=router):
            self.assertIsNone(_run(tts.synthesize("No rate given.")))

    def test_local_voice_alone_counts_as_available(self) -> None:
        with patch.multiple(tts.settings, llm_provider="openai", llm_api_key=""):
            self.assertTrue(tts.is_available())

    def test_prefer_gemini_reverses_the_order(self) -> None:
        router = _Router(_LocalResponse(content=b""), _Response(200, _audio_payload(b"		")))
        with patch.dict("os.environ", {"TTS_PREFER": "gemini"}), patch(
            "app.services.llm_client.get_http_client", return_value=router
        ):
            _run(tts.synthesize("Gemini first, please."))
        self.assertEqual(router.calls, ["gemini"])

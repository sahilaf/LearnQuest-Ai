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

    def tearDown(self) -> None:
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
            first = _run(tts.synthesize("Nova says this twice."))
            second = _run(tts.synthesize("Nova says this twice."))

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

        async def _fake(text):  # noqa: ANN001
            return speech

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, pcm)
        self.assertEqual(response.headers["X-Sample-Rate"], "24000")
        self.assertIn("rate=24000", response.headers["content-type"])

    def test_mismatched_rate_is_refused_rather_than_shipped(self) -> None:
        async def _fake(text):  # noqa: ANN001
            return tts.Speech(pcm=b"\x00\x01" * 100, sample_rate=16000)

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 503)

    def test_no_voice_is_a_503(self) -> None:
        async def _fake(text):  # noqa: ANN001
            return None

        with patch("app.routers.avatar.synthesize", _fake):
            response = self._client().post("/api/avatar/speech", json={"text": "hello"})

        self.assertEqual(response.status_code, 503)

    def test_empty_text_is_a_400(self) -> None:
        response = self._client().post("/api/avatar/speech", json={"text": "   "})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

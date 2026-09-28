"""Gemini model fallback: an overloaded model must not fail the request.

Measured 2026-09-29: a notes upload failed after three 503s from
gemini-3.6-flash in 12 seconds, while gemini-3.7-flash and gemini-2.5-flash
answered in about two. The client used to retry the same model; it now moves
to the next one.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import httpx

from app.services import llm_client
from app.services.jobs import _student_facing_error
from app.services.llm_client import GeminiClient, LLMError


def _run(coro):
    return asyncio.run(coro)


def _response(status: int, text: str = "ok", url: str = "https://x/models/m:generateContent"):
    request = httpx.Request("POST", url)
    if status == 200:
        body = {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {}}
    else:
        body = {"error": {"status": "UNAVAILABLE"}}
    return httpx.Response(status, json=body, request=request)


class _FakeHTTP:
    """Answers per model name, and records which models were asked."""

    def __init__(self, status_by_model: dict[str, int]):
        self.status_by_model = status_by_model
        self.calls: list[str] = []
        self.bodies: list[dict] = []

    async def post(self, url, headers=None, json=None):
        model = url.split("/models/")[1].split(":")[0]
        self.calls.append(model)
        self.bodies.append(json)
        return _response(self.status_by_model.get(model, 200), text=f"from {model}", url=url)


async def _no_sleep(_seconds):
    return None


class TestCompleteFallback(unittest.TestCase):
    def _complete(self, client, http):
        with patch.object(llm_client, "get_http_client", return_value=http), patch.object(
            llm_client.asyncio, "sleep", _no_sleep
        ):
            return _run(client.complete([{"role": "user", "content": "hi"}]))

    def test_an_overloaded_model_falls_through_to_the_next(self) -> None:
        client = GeminiClient("k", "gemini-3.6-flash", ["gemini-3.7-flash", "gemini-2.5-flash"])
        http = _FakeHTTP({"gemini-3.6-flash": 503})
        self.assertEqual(self._complete(client, http), "from gemini-3.7-flash")
        # Straight to the next model - no waiting on the overloaded one.
        self.assertEqual(http.calls, ["gemini-3.6-flash", "gemini-3.7-flash"])

    def test_a_quota_error_falls_through_too(self) -> None:
        """The free-tier daily quota is per model."""
        client = GeminiClient("k", "gemini-3.6-flash", ["gemini-2.5-flash"])
        http = _FakeHTTP({"gemini-3.6-flash": 429})
        self.assertEqual(self._complete(client, http), "from gemini-2.5-flash")

    def test_an_empty_reply_falls_through_instead_of_returning_blank(self) -> None:
        """Blank text read downstream as "these notes have no study material"."""
        client = GeminiClient("k", "gemini-3.7-flash", ["gemini-2.5-flash"])
        http = _FakeHTTP({})
        original = http.post

        async def post(url, headers=None, json=None):
            response = await original(url, headers=headers, json=json)
            if "gemini-3.7-flash" in url:
                return httpx.Response(
                    200,
                    json={"candidates": [{"content": {"parts": []}, "finishReason": "OTHER"}]},
                    request=response.request,
                )
            return response

        http.post = post
        self.assertEqual(self._complete(client, http), "from gemini-2.5-flash")

    def test_the_primary_is_used_when_it_works(self) -> None:
        client = GeminiClient("k", "gemini-3.6-flash", ["gemini-2.5-flash"])
        http = _FakeHTTP({})
        self.assertEqual(self._complete(client, http), "from gemini-3.6-flash")
        self.assertEqual(http.calls, ["gemini-3.6-flash"])

    def test_all_models_down_goes_round_again_then_raises(self) -> None:
        client = GeminiClient("k", "a-model", ["b-model"])
        http = _FakeHTTP({"a-model": 503, "b-model": 503})
        with patch.object(llm_client.settings, "llm_max_retries", 1):
            with self.assertRaises(LLMError):
                self._complete(client, http)
        self.assertEqual(http.calls, ["a-model", "b-model", "a-model", "b-model"])

    def test_no_fallbacks_behaves_as_before(self) -> None:
        client = GeminiClient("k", "gemini-3.6-flash")
        self.assertEqual(client.models, ["gemini-3.6-flash"])

    def test_duplicates_and_prefixes_are_cleaned(self) -> None:
        client = GeminiClient("k", "models/gemini-3.6-flash", ["gemini-3.6-flash", "models/gemini-2.5-flash", ""])
        self.assertEqual(client.models, ["gemini-3.6-flash", "gemini-2.5-flash"])

    def test_thinking_config_follows_the_model_actually_called(self) -> None:
        """A legacy fallback must not be sent a field it rejects."""
        client = GeminiClient("k", "gemini-3.6-flash", ["gemini-2.0-flash"])
        http = _FakeHTTP({"gemini-3.6-flash": 503})
        self._complete(client, http)
        self.assertIn("thinkingConfig", http.bodies[0]["generationConfig"])
        self.assertNotIn("thinkingConfig", http.bodies[1]["generationConfig"])


class TestStudentFacingError(unittest.TestCase):
    def test_a_503_says_the_service_is_busy(self) -> None:
        message = _student_facing_error(RuntimeError("Server error '503 Service Unavailable'"))
        self.assertIn("busy", message)

    def test_a_429_still_says_rate_limited(self) -> None:
        self.assertIn("request limit", _student_facing_error(RuntimeError("429 Too Many Requests")))


if __name__ == "__main__":
    unittest.main()

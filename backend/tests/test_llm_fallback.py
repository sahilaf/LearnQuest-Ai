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


class TestGemma(unittest.TestCase):
    """gemma-4-31b-it rejects three things the flash models accept (2026-09-29)."""

    def _payload(self, messages, json_mode=False):
        client = GeminiClient("k", "gemini-3.6-flash", ["gemma-4-31b-it"])
        return client._prepare_payload(messages, 0.5, 800, json_mode, "gemma-4-31b-it")

    def test_system_instruction_is_folded_into_the_first_user_turn(self) -> None:
        body = self._payload(
            [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Hi"}]
        )
        self.assertNotIn("systemInstruction", body)  # 500 on Gemma
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "Be brief.\n\nHi")

    def test_thinking_uses_level_not_budget(self) -> None:
        config = self._payload([{"role": "user", "content": "Hi"}])["generationConfig"]
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "minimal"})  # budget -> 400
        self.assertGreater(config["maxOutputTokens"], 800)  # room left to answer

    def test_flash_models_are_unchanged(self) -> None:
        client = GeminiClient("k", "gemini-3.6-flash", ["gemma-4-31b-it"])
        body = client._prepare_payload(
            [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], 0.5, 800, False
        )
        self.assertIn("systemInstruction", body)
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 800)
        self.assertIn("thinkingBudget", body["generationConfig"]["thinkingConfig"])

    def test_thought_parts_are_not_returned_as_the_answer(self) -> None:
        client = GeminiClient("k", "gemma-4-31b-it")

        class _HTTP:
            async def post(self, url, headers=None, json=None, **kwargs):
                return httpx.Response(
                    200,
                    json={"candidates": [{"content": {"parts": [
                        {"text": "Let me think about colours...", "thought": True},
                        {"text": "Red and blue."},
                    ]}}]},
                    request=httpx.Request("POST", url),
                )

        with patch.object(llm_client, "get_http_client", return_value=_HTTP()):
            self.assertEqual(_run(client.complete([{"role": "user", "content": "x"}])), "Red and blue.")

    def test_gemma_gets_a_longer_timeout(self) -> None:
        client = GeminiClient("k", "gemini-3.6-flash", ["gemma-4-31b-it"])
        seen = {}

        class _HTTP:
            async def post(self, url, headers=None, json=None, **kwargs):
                model = url.split("/models/")[1].split(":")[0]
                seen[model] = kwargs.get("timeout")
                status = 503 if model == "gemini-3.6-flash" else 200
                return _response(status, url=url)

        with patch.object(llm_client, "get_http_client", return_value=_HTTP()):
            _run(client.complete([{"role": "user", "content": "x"}]))
        self.assertIsNone(seen["gemini-3.6-flash"])
        self.assertEqual(seen["gemma-4-31b-it"], GeminiClient.GEMMA_TIMEOUT_SECONDS)

    def test_streaming_skips_gemma(self) -> None:
        client = GeminiClient("k", "gemma-4-31b-it")

        async def consume():
            return [t async for t in client.stream([{"role": "user", "content": "x"}])]

        with self.assertRaises(LLMError) as ctx:
            _run(consume())
        self.assertIn("streaming", str(ctx.exception))


class _Scripted(llm_client.LLMClient):
    def __init__(self, reply=None, error=None, stream_tokens=None, stream_error_after=None):
        self.reply, self.error = reply, error
        self.stream_tokens = stream_tokens or []
        self.stream_error_after = stream_error_after
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise LLMError(self.error)
        return self.reply

    async def stream(self, messages, **kwargs):
        for i, token in enumerate(self.stream_tokens):
            if self.stream_error_after is not None and i == self.stream_error_after:
                raise LLMError("dropped mid-stream")
            yield token
        if self.error:
            raise LLMError(self.error)


class TestChain(unittest.TestCase):
    def _run_complete(self, chain):
        with patch.object(llm_client.asyncio, "sleep", _no_sleep):
            return _run(chain.complete([{"role": "user", "content": "x"}]))

    def test_second_provider_answers_when_the_first_is_down(self) -> None:
        gemini, openrouter = _Scripted(error="503"), _Scripted(reply="from openrouter")
        chain = llm_client.ChainClient([gemini, openrouter])
        self.assertEqual(self._run_complete(chain), "from openrouter")

    def test_first_provider_is_preferred(self) -> None:
        gemini, openrouter = _Scripted(reply="from gemini"), _Scripted(reply="from openrouter")
        self.assertEqual(self._run_complete(llm_client.ChainClient([gemini, openrouter])), "from gemini")
        self.assertEqual(openrouter.calls, 0)

    def test_all_down_retries_in_rounds_then_raises(self) -> None:
        a, b = _Scripted(error="503"), _Scripted(error="402 no credit")
        with patch.object(llm_client.settings, "llm_max_retries", 1):
            with self.assertRaises(LLMError):
                self._run_complete(llm_client.ChainClient([a, b]))
        self.assertEqual((a.calls, b.calls), (2, 2))

    def test_stream_falls_back_before_the_first_token(self) -> None:
        chain = llm_client.ChainClient(
            [_Scripted(error="503"), _Scripted(stream_tokens=["Hel", "lo"])]
        )

        async def consume():
            return "".join([t async for t in chain.stream([{"role": "user", "content": "x"}])])

        self.assertEqual(_run(consume()), "Hello")

    def test_stream_never_splices_two_answers(self) -> None:
        chain = llm_client.ChainClient(
            [_Scripted(stream_tokens=["Half an ", "answer"], stream_error_after=1),
             _Scripted(stream_tokens=["Another answer"])]
        )

        async def consume():
            return [t async for t in chain.stream([{"role": "user", "content": "x"}])]

        with self.assertRaises(LLMError):
            _run(consume())


class TestGetLLMWiring(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = llm_client._client
        llm_client._client = None

    def tearDown(self) -> None:
        llm_client._client = self._saved

    def _build(self, **overrides):
        values = {
            "llm_provider": "gemini",
            "llm_api_key": "g-key",
            "llm_model": "gemini-3.6-flash",
            "llm_fallback_models": "gemini-2.5-flash",
            "openrouter_api_key": "",
            "openrouter_model": "inclusionai/ling-3.0-flash-vl",
            "llm_primary": "gemini",
        }
        values.update(overrides)
        with patch.multiple(llm_client.settings, **values):
            return llm_client.get_llm()

    def test_openrouter_key_adds_a_second_provider(self) -> None:
        client = self._build(openrouter_api_key="or-key")
        self.assertIsInstance(client, llm_client.ChainClient)
        gemini, openrouter = client.clients
        self.assertEqual(gemini.models, ["gemini-3.6-flash", "gemini-2.5-flash"])
        self.assertEqual(gemini.rounds, 1)  # the chain does the waiting
        self.assertEqual(openrouter.model, "inclusionai/ling-3.0-flash-vl")
        self.assertEqual(openrouter.retries, 0)
        self.assertIn("openrouter.ai", openrouter.base_url)

    def test_openrouter_can_be_primary_with_gemini_as_fallback(self) -> None:
        client = self._build(openrouter_api_key="or-key", llm_primary="openrouter")
        first, second = client.clients
        self.assertIsInstance(first, llm_client.OpenAICompatibleClient)
        self.assertIn("openrouter.ai", first.base_url)
        self.assertIsInstance(second, GeminiClient)
        self.assertEqual(second.rounds, 1)

    def test_no_openrouter_key_keeps_gemini_alone(self) -> None:
        self.assertIsInstance(self._build(), GeminiClient)

    def test_mock_is_never_chained_to_a_paid_provider(self) -> None:
        client = self._build(llm_provider="mock", openrouter_api_key="or-key")
        self.assertIsInstance(client, llm_client.MockLLMClient)


class TestOpenRouterReasoning(unittest.TestCase):
    def test_openrouter_is_given_its_backup_models(self) -> None:
        """Ling has one upstream; its 429s are served by the next model."""
        orc = llm_client.OpenAICompatibleClient(
            llm_client.PROVIDER_ENDPOINTS["openrouter"], "k", "inclusionai/ling-3.0-flash-vl",
            fallback_models=["google/gemini-2.5-flash-lite", "inclusionai/ling-3.0-flash-vl", ""],
        )
        self.assertEqual(
            orc._extras()["models"],
            ["inclusionai/ling-3.0-flash-vl", "google/gemini-2.5-flash-lite"],
        )

    def test_reasoning_is_off_for_openrouter_only(self) -> None:
        orc = llm_client.OpenAICompatibleClient(llm_client.PROVIDER_ENDPOINTS["openrouter"], "k", "m")
        groq = llm_client.OpenAICompatibleClient(llm_client.PROVIDER_ENDPOINTS["groq"], "k", "m")
        self.assertEqual(orc._extras(), {"reasoning": {"enabled": False}})
        self.assertEqual(groq._extras(), {})


class TestOpenAICompatibleEmptyReply(unittest.TestCase):
    def test_an_empty_reply_is_a_failure(self) -> None:
        client = llm_client.OpenAICompatibleClient("https://x/chat/completions", "k", "m", retries=0)

        class _HTTP:
            async def post(self, url, headers=None, json=None, **kwargs):
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": None}}]},
                    request=httpx.Request("POST", url),
                )

        with patch.object(llm_client, "get_http_client", return_value=_HTTP()):
            with self.assertRaises(LLMError):
                _run(client.complete([{"role": "user", "content": "x"}]))


class TestStudentFacingError(unittest.TestCase):
    def test_a_503_says_the_service_is_busy(self) -> None:
        message = _student_facing_error(RuntimeError("Server error '503 Service Unavailable'"))
        self.assertIn("busy", message)

    def test_a_429_still_says_rate_limited(self) -> None:
        self.assertIn("request limit", _student_facing_error(RuntimeError("429 Too Many Requests")))


if __name__ == "__main__":
    unittest.main()

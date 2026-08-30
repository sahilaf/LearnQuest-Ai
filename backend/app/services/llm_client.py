"""LLM abstraction layer.

OWNER: Member 1. See plan.md 6.2.

Every AI call in the project goes through this interface, so swapping providers
costs ten minutes instead of a rewrite.

    from app.services.llm_client import get_llm
    reply = await get_llm().complete([{"role": "user", "content": "hi"}])

Set LLM_PROVIDER=mock to run the entire app with no API key - this is what lets
Members 2, 3 and 4 work without waiting on the lead.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger("learnquest.llm")

PROVIDER_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}


class LLMError(RuntimeError):
    """Raised when the provider fails after all retries."""


class LLMClient:
    """Base interface. Implementations must not raise anything but LLMError."""

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        raise NotImplementedError

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""  # pragma: no cover - makes this an async generator


class MockLLMClient(LLMClient):
    """Deterministic offline stand-in. No network, no key, no cost."""

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        last = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        if json_mode:
            return json.dumps(
                {
                    "questions": [
                        {
                            "type": "mcq",
                            "prompt": "[mock] Which statement about this topic is true?",
                            "options": ["Option A", "Option B", "Option C", "Option D"],
                            "correct_answer": "Option B",
                            "explanation": "[mock] Option B matches the lesson material.",
                            "topic_tag": "mock.topic",
                            "difficulty": "medium",
                        }
                    ]
                }
            )
        return (
            "[mock tutor] Good question. Before I answer, what do you already know "
            f"about \"{last[:60]}\"? Set LLM_PROVIDER to a real provider for live answers."
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        text = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        for word in text.split(" "):
            await asyncio.sleep(0.02)
            yield word + " "


class OpenAICompatibleClient(LLMClient):
    """Works for Groq and OpenAI - both speak the /chat/completions schema."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
                    resp = await http.post(self.base_url, headers=self._headers, json=body)
                    resp.raise_for_status()
                    data = resp.json()
                usage = data.get("usage", {})
                logger.info(
                    "llm complete model=%s tokens=%s", self.model, usage.get("total_tokens")
                )
                return data["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = 2**attempt
                logger.warning("llm attempt %s failed: %s (retry in %ss)", attempt + 1, exc, wait)
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(wait)

        raise LLMError(f"LLM request failed after retries: {last_error}") from last_error

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
                async with http.stream(
                    "POST", self.base_url, headers=self._headers, json=body
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = json.loads(chunk)["choices"][0]["delta"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if content := delta.get("content"):
                            yield content
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"LLM stream failed: {exc}") from exc


class GeminiClient(LLMClient):
    """TODO(M1): implement if LLM_PROVIDER=gemini is chosen (plan.md 6.2)."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, messages, *, temperature=0.7, max_tokens=800, json_mode=False) -> str:
        raise LLMError("Gemini client not implemented yet - see plan.md 6.2.")

    async def stream(self, messages, *, temperature=0.7, max_tokens=800) -> AsyncIterator[str]:
        raise LLMError("Gemini client not implemented yet - see plan.md 6.2.")
        yield ""  # pragma: no cover


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """Return the configured client. Falls back to the mock when no key is set."""
    global _client
    if _client is not None:
        return _client

    provider = settings.llm_provider.lower()

    if provider == "mock" or not settings.llm_api_key:
        if provider != "mock":
            logger.warning("LLM_API_KEY is empty - falling back to MockLLMClient.")
        _client = MockLLMClient()
    elif provider in PROVIDER_ENDPOINTS:
        _client = OpenAICompatibleClient(
            PROVIDER_ENDPOINTS[provider], settings.llm_api_key, settings.llm_model
        )
    elif provider == "gemini":
        _client = GeminiClient(settings.llm_api_key, settings.llm_model)
    else:
        logger.error("Unknown LLM_PROVIDER %r - falling back to MockLLMClient.", provider)
        _client = MockLLMClient()

    logger.info("LLM client: %s", type(_client).__name__)
    return _client

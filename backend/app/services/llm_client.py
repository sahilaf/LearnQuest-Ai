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


_shared_http: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Process-wide HTTP client for provider calls.

    Every request previously opened its own ``httpx.AsyncClient``, which threw
    away the connection pool afterwards - so each LLM call paid a fresh DNS
    lookup, TCP connect and TLS handshake to a remote provider. Reusing one
    client keeps the connection alive between calls.
    """
    global _shared_http
    if _shared_http is None or _shared_http.is_closed:
        _shared_http = httpx.AsyncClient(
            timeout=settings.llm_timeout_seconds,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _shared_http


async def close_http_client() -> None:
    """Release the shared client on application shutdown."""
    global _shared_http
    if _shared_http is not None and not _shared_http.is_closed:
        await _shared_http.aclose()
    _shared_http = None


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
                http = get_http_client()
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
            http = get_http_client()
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
    """Google Gemini client speaking the Generative Language REST API.

    Supports gemini-2.5-flash, gemini-2.5-pro, gemini-flash-latest, etc.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        raw_model = model or "gemini-2.5-flash"
        self.model = raw_model.removeprefix("models/")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self) -> dict[str, str]:
        """Auth goes in a header, never in the query string.

        Gemini accepts `?key=...`, and that is how this client used to send it -
        which meant httpx put the full URL into every error it raised, so a
        single 429 wrote the API key into the application log in plain text.
        A header is never echoed back in an exception message.
        """
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def _supports_thinking(self) -> bool:
        """True for Gemini families that accept generationConfig.thinkingConfig."""
        legacy = ("1.0", "1.5", "2.0")
        return not any(tag in self.model for tag in legacy)

    def _prepare_payload(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> dict:
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        generation_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        # Thinking tokens come out of maxOutputTokens. Left unset, a 2.5 model
        # spends nearly the whole budget reasoning and the reply is truncated
        # mid-sentence with finishReason=MAX_TOKENS. Legacy 1.5/2.0 models do
        # not accept this field, so only send it where it applies.
        if self._supports_thinking():
            generation_config["thinkingConfig"] = {
                "thinkingBudget": settings.llm_thinking_budget
            }

        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        body: dict = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction
        return body

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        body = self._prepare_payload(messages, temperature, max_tokens, json_mode)
        endpoint = f"{self.base_url}/models/{self.model}:generateContent"

        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                http = get_http_client()
                resp = await http.post(
                    endpoint,
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMError(f"Gemini returned no candidates: {data}")

                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                usage = data.get("usageMetadata", {})
                logger.info(
                    "gemini complete model=%s tokens=%s",
                    self.model,
                    usage.get("totalTokenCount"),
                )
                return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = 2**attempt
                logger.warning(
                    "gemini attempt %s failed: %s (retry in %ss)", attempt + 1, exc, wait
                )
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(wait)

        raise LLMError(f"Gemini request failed after retries: {last_error}") from last_error

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        body = self._prepare_payload(messages, temperature, max_tokens, False)
        endpoint = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse"

        try:
            http = get_http_client()
            async with http.stream(
                "POST",
                endpoint,
                headers=self._headers(),
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk_str = line[6:].strip()
                    if not chunk_str or chunk_str == "[DONE]":
                        continue
                    try:
                        chunk_data = json.loads(chunk_str)
                        candidates = chunk_data.get("candidates", [])
                        if candidates:
                            for part in candidates[0].get("content", {}).get("parts", []):
                                if text := part.get("text"):
                                    yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini stream failed: {exc}") from exc


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

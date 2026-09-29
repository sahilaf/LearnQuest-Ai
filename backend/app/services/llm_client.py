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
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
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
    """Works for Groq, OpenAI and OpenRouter - all speak /chat/completions.

    `retries` defaults to LLM_MAX_RETRIES; a `ChainClient` passes 0 so that it,
    not each provider, decides when to wait and go round again.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        retries: int | None = None,
        fallback_models: list[str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.retries = settings.llm_max_retries if retries is None else retries
        # OpenRouter only: backup models it tries itself, within one request.
        self.fallback_models = [m for m in (fallback_models or []) if m and m != model]

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extras(self) -> dict:
        """Provider-specific body fields.

        OpenRouter: reasoning off, the same policy as `llm_thinking_budget=0`
        for Gemini. Measured 2026-09-29 on inclusionai/ling-3.0-flash-vl, the
        default spent 187 of 284 output tokens reasoning, and on a longer reply
        ran out of budget mid-JSON (unparseable). Off: 2.7s instead of 5.5s,
        valid every time.
        """
        if "openrouter.ai" in self.base_url:
            extras: dict = {"reasoning": {"enabled": False}}
            if self.fallback_models:
                # OpenRouter's model routing: on an error from the first model
                # (e.g. its only upstream rate-limiting it) it serves the next.
                extras["models"] = [self.model, *self.fallback_models]
            return extras
        return {}

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
            **self._extras(),
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                http = get_http_client()
                resp = await http.post(self.base_url, headers=self._headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                text = data["choices"][0]["message"].get("content") or ""
                # Same rule as the Gemini client: an empty 200 is a failure,
                # not an answer that downstream code will misread.
                if not text.strip():
                    raise LLMError(f"{self.model} returned no text")
                logger.info(
                    "llm complete model=%s tokens=%s", self.model, usage.get("total_tokens")
                )
                return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = 2**attempt
                logger.warning("llm %s attempt %s failed: %s", self.model, attempt + 1, exc)
                if attempt < self.retries:
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
            **self._extras(),
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

    Fallback models
    ---------------
    `models` is the configured model followed by `LLM_FALLBACK_MODELS`. A 503
    means *that model* is overloaded, and it tends to stay overloaded for
    minutes; retrying it 1s, 2s and 4s later - what this client used to do -
    failed a notes upload in 12 seconds while other models answered in two. So
    each attempt moves to the next model, and only a full pass over all of
    them waits before starting again. The free-tier daily quota is per model
    too, so the same rotation gets past a 429.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        fallbacks: list[str] | None = None,
        rounds: int | None = None,
    ) -> None:
        self.api_key = api_key
        # Full passes over `models`. A ChainClient passes 1 and does its own
        # rounds, so a second provider is tried before any waiting.
        self.rounds = rounds
        raw_model = model or "gemini-2.5-flash"
        self.model = raw_model.removeprefix("models/")
        self.models: list[str] = []
        for name in [self.model, *(fallbacks or [])]:
            name = name.removeprefix("models/")
            if name and name not in self.models:
                self.models.append(name)
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

    @staticmethod
    def _supports_thinking(model: str) -> bool:
        """True for Gemini families that accept generationConfig.thinkingConfig."""
        legacy = ("1.0", "1.5", "2.0")
        return not any(tag in model for tag in legacy)

    # Gemma through this same API (e.g. gemma-4-31b-it) has a far larger free
    # quota - 14.4K requests/day against the flash models' few hundred - but
    # measured 2026-09-29 it differs in four ways that each break a request:
    #
    #   systemInstruction   -> 500. Folded into the first user turn instead.
    #   thinkingBudget      -> 400 "not supported". It thinks by default and
    #                          spent a whole 60-token cap on it, returning no
    #                          answer; thinkingLevel="minimal" is accepted.
    #   streaming           -> 500. Skipped by stream().
    #   latency             -> 37-66s where flash takes 2-6s, so it gets its
    #                          own longer timeout and belongs at the END of
    #                          LLM_FALLBACK_MODELS, not the front.
    #
    # It also returned intermittent 500s for identical requests, which the
    # fallback rotation absorbs like any other failure.
    GEMMA_TIMEOUT_SECONDS = 120
    GEMMA_THINKING_HEADROOM = 512

    @staticmethod
    def _is_gemma(model: str) -> bool:
        return model.startswith("gemma")

    def _prepare_payload(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        model: str | None = None,
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

        model = model or self.model
        gemma = self._is_gemma(model)

        if gemma and system_instruction:
            # No systemInstruction on Gemma: prepend it to the first user turn.
            text = system_instruction["parts"][0]["text"]
            first_user = next((c for c in contents if c["role"] == "user"), None)
            if first_user is not None:
                first_user["parts"][0]["text"] = f"{text}\n\n{first_user['parts'][0]['text']}"
            else:
                contents.insert(0, {"role": "user", "parts": [{"text": text}]})
            system_instruction = None

        generation_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens + (self.GEMMA_THINKING_HEADROOM if gemma else 0),
        }

        # Thinking tokens come out of maxOutputTokens. Left unset, a 2.5 model
        # spends nearly the whole budget reasoning and the reply is truncated
        # mid-sentence with finishReason=MAX_TOKENS. Legacy 1.5/2.0 models do
        # not accept this field, so only send it where it applies.
        if gemma:
            generation_config["thinkingConfig"] = {"thinkingLevel": "minimal"}
        elif self._supports_thinking(model):
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
        last_error: Exception | None = None
        rounds = self.rounds or settings.llm_max_retries + 1
        for round_ in range(rounds):
            for model in self.models:
                body = self._prepare_payload(messages, temperature, max_tokens, json_mode, model)
                endpoint = f"{self.base_url}/models/{model}:generateContent"
                try:
                    http = get_http_client()
                    extra = (
                        {"timeout": self.GEMMA_TIMEOUT_SECONDS} if self._is_gemma(model) else {}
                    )
                    resp = await http.post(endpoint, headers=self._headers(), json=body, **extra)
                    resp.raise_for_status()
                    data = resp.json()

                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise LLMError(f"Gemini returned no candidates: {data}")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    # Thinking models may return their reasoning as parts marked
                    # `thought: true`. That is not the answer, and in JSON mode
                    # it would make the reply unparseable.
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    # A 200 with no text happens (seen 2026-09-29 on
                    # gemini-3.7-flash). Returned as "", it reads downstream as
                    # "the notes had no study material" - blaming the student's
                    # file for a model hiccup. Treat it as a failure instead.
                    if not text.strip():
                        raise LLMError(
                            "Gemini returned no text "
                            f"(finishReason={candidates[0].get('finishReason')})"
                        )
                    usage = data.get("usageMetadata", {})
                    logger.info(
                        "gemini complete model=%s tokens=%s%s",
                        model,
                        usage.get("totalTokenCount"),
                        "" if model == self.model else " (fallback)",
                    )
                    return text
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning("gemini %s failed: %s", model, exc)

            # Every model failed this round. Back off before going round again.
            if round_ < rounds - 1:
                wait = 2**round_
                logger.warning(
                    "gemini: all %d model(s) failed, retry in %ss", len(self.models), wait
                )
                await asyncio.sleep(wait)

        raise LLMError(f"Gemini request failed after retries: {last_error}") from last_error

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        # Falls back only before the first token. Once text has reached the
        # student, switching model would splice two different answers together.
        last_error: Exception | None = None
        for model in self.models:
            if self._is_gemma(model):
                continue  # Gemma does not stream on this API (500), see above.
            body = self._prepare_payload(messages, temperature, max_tokens, False, model)
            endpoint = f"{self.base_url}/models/{model}:streamGenerateContent?alt=sse"
            started = False
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
                                    if part.get("thought"):
                                        continue
                                    if text := part.get("text"):
                                        started = True
                                        yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                return
            except Exception as exc:  # noqa: BLE001
                if started:
                    raise LLMError(f"Gemini stream failed: {exc}") from exc
                last_error = exc
                logger.warning("gemini stream %s failed before any output: %s", model, exc)

        if last_error is None:
            raise LLMError("No configured Gemini model supports streaming.")
        raise LLMError(f"Gemini stream failed: {last_error}") from last_error


class ChainClient(LLMClient):
    """Several providers in order: each gets one pass, then the chain waits.

    Built by `get_llm()` when a second provider is configured. Without it, an
    outage or daily quota at the primary provider fails every AI feature at
    once - the tutor, grading, the misconception engine, course generation -
    however many models that provider offers.
    """

    def __init__(self, clients: list[LLMClient]) -> None:
        self.clients = clients

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        last_error: Exception | None = None
        rounds = settings.llm_max_retries + 1
        for round_ in range(rounds):
            for client in self.clients:
                try:
                    return await client.complete(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning("provider %s failed: %s", type(client).__name__, exc)
            if round_ < rounds - 1:
                await asyncio.sleep(2**round_)
        raise LLMError(f"Every provider failed: {last_error}") from last_error

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> AsyncIterator[str]:
        # Moves on only before the first token, for the same reason as
        # GeminiClient.stream: never splice two answers together.
        last_error: Exception | None = None
        for client in self.clients:
            started = False
            try:
                async for text in client.stream(
                    messages, temperature=temperature, max_tokens=max_tokens
                ):
                    started = True
                    yield text
                return
            except Exception as exc:  # noqa: BLE001
                if started:
                    raise
                last_error = exc
                logger.warning("provider %s stream failed: %s", type(client).__name__, exc)
        raise LLMError(f"Every provider failed to stream: {last_error}") from last_error


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """Return the configured client. Falls back to the mock when no key is set."""
    global _client
    if _client is not None:
        return _client

    provider = settings.llm_provider.lower()
    chained = bool(settings.openrouter_api_key) and provider != "openrouter"

    if provider == "mock" or not settings.llm_api_key:
        if provider != "mock":
            logger.warning("LLM_API_KEY is empty - falling back to MockLLMClient.")
        _client = MockLLMClient()
        chained = False
    elif provider in PROVIDER_ENDPOINTS:
        _client = OpenAICompatibleClient(
            PROVIDER_ENDPOINTS[provider],
            settings.llm_api_key,
            settings.llm_model,
            retries=0 if chained else None,
        )
    elif provider == "gemini":
        _client = GeminiClient(
            settings.llm_api_key,
            settings.llm_model,
            settings.llm_fallback_model_list,
            rounds=1 if chained else None,
        )
    else:
        logger.error("Unknown LLM_PROVIDER %r - falling back to MockLLMClient.", provider)
        _client = MockLLMClient()
        chained = False

    if chained:
        openrouter = OpenAICompatibleClient(
            PROVIDER_ENDPOINTS["openrouter"],
            settings.openrouter_api_key,
            settings.openrouter_model,
            retries=0,
            fallback_models=settings.openrouter_fallback_model_list,
        )
        # LLM_PRIMARY picks who is asked first; the other is the fallback.
        order = (
            [openrouter, _client]
            if settings.llm_primary.strip().lower() == "openrouter"
            else [_client, openrouter]
        )
        _client = ChainClient(order)

    logger.info("LLM client: %s", type(_client).__name__)
    return _client

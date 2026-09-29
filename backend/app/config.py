"""Application settings. SHARED FILE - change only by agreement (plan.md 2.4)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    app_env: str = "development"
    # Vite falls back to 5174/5175 when 5173 is taken (a second dev server,
    # a stray process). Allowing the fallbacks avoids every request failing
    # CORS preflight just because the frontend moved port.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175"

    # --- database (M3) ---
    database_url: str = ""

    # --- auth: Supabase Auth (M3) ---
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""
    # Dev escape hatch: requests without a token get a fake user. It must be
    # opted INTO, never defaulted on - a deploy that forgets to set it would
    # otherwise serve every endpoint to anonymous callers, and nothing would
    # look wrong. `is_production` below refuses it outright.
    dev_allow_anonymous: bool = False
    jwt_leeway_seconds: int = 7200

    # --- llm (M1) ---
    llm_provider: str = "mock"
    llm_api_key: str = ""
    # Gemini 2.5+ are "thinking" models: internal reasoning is billed against
    # maxOutputTokens, so a small cap leaves nothing for the visible answer
    # (measured: 237 of 250 tokens went to thinking, answer truncated at 31
    # chars). 0 disables thinking; raise it only if you also raise max_tokens.
    llm_thinking_budget: int = 0
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    # Comma-separated Gemini models tried in order when `llm_model` fails.
    # A 503 ("overloaded") is per model and usually lasts minutes, so retrying
    # the same model a few seconds later rarely helps - measured 2026-09-29, an
    # upload failed on three 503s in 12s while other models answered in 2s.
    # The free-tier daily quota is also per model, so this covers 429s too.
    llm_fallback_models: str = ""
    # A second *provider*, tried when every model above has failed. OpenRouter
    # speaks the OpenAI schema; the default is cheap (~$0.00005 per lesson,
    # measured 2026-09-29), fast (~5s) and returned valid JSON first time.
    # It is paid: the account needs credit. Empty key = no second provider.
    openrouter_api_key: str = ""
    openrouter_model: str = "inclusionai/ling-3.0-flash-vl"
    # Tried by OpenRouter itself, in the same request, when the model above
    # errors. Ling is served by a single upstream (Novita), which returned
    # "temporarily rate-limited" 429s on 2026-09-29; gemini-2.5-flash-lite is
    # served by Google (a separate quota from AI Studio's free tier), returned
    # valid JSON in 0.8s, and costs ~5x Ling - still ~$0.0003 per lesson.
    openrouter_fallback_models: str = "google/gemini-2.5-flash-lite"
    # Which provider the chain asks first when both are configured:
    # "gemini" (free, but a per-model daily quota) or "openrouter" (paid, but
    # no quota wall). With Gemini first, a used-up quota made every AI call
    # fail through four Gemini models before reaching OpenRouter - 5-20s per
    # call, which is what held database connections long enough to exhaust
    # the pool on 2026-09-29.
    llm_primary: str = "gemini"

    # --- avatar (M1) ---
    avatar_service_url: str = ""

    @property
    def llm_fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.llm_fallback_models.split(",") if m.strip()]

    @property
    def openrouter_fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.openrouter_fallback_models.split(",") if m.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def allow_anonymous(self) -> bool:
        """Whether unauthenticated requests get a dev user.

        Never in production, whatever the environment says. The previous code
        logged an error and then served the request anyway, which is the worst
        of both: it looks handled in the logs and is wide open in fact.
        """
        return self.dev_allow_anonymous and not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

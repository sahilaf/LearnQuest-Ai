"""Application settings. SHARED FILE - change only by agreement (plan.md 2.4)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- database (M3) ---
    database_url: str = ""

    # --- auth: Supabase Auth (M3) ---
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""
    dev_allow_anonymous: bool = True

    # --- llm (M1) ---
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # --- avatar (M1) ---
    avatar_service_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

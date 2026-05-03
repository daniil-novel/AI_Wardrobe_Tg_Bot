from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    public_api_url: str = "http://localhost:8000"
    internal_api_url: str = ""
    miniapp_public_url: str = "https://your-tunnel.example"

    database_url: str = "postgresql+asyncpg://ai_wardrobe:change-me@postgres:5432/ai_wardrobe"
    sync_database_url: str = "postgresql+psycopg://ai_wardrobe:change-me@postgres:5432/ai_wardrobe"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    jwt_secret_key: str = "replace-with-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_image: str = "google/gemini-pro-latest"
    openrouter_model_text: str = "google/gemini-pro-latest"
    ai_daily_budget_usd: float = 20

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "ai-wardrobe-private"
    s3_region: str = "us-east-1"
    signed_url_ttl_seconds: int = 900

    free_items_limit: int = 20
    free_ai_analyses_per_month: int = 5
    premium_items_limit: int = 500
    premium_ai_analyses_per_month: int = 100

    telegram_payment_provider_token: str = ""
    external_payment_provider_url: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing_runtime_secrets(self) -> list[str]:
        missing: list[str] = []
        for field_name in ("telegram_bot_token", "openrouter_api_key", "jwt_secret_key"):
            value = getattr(self, field_name)
            if not value or value == "replace-with-a-long-random-secret":
                missing.append(field_name.upper())
        return missing

    @computed_field  # type: ignore[prop-decorator]
    @property
    def real_ai_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def real_telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

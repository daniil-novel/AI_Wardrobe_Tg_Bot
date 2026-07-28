from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    log_dir: str = ""
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
    openrouter_model_image: str = "google/gemini-2.5-pro"
    openrouter_model_text: str = "google/gemini-2.5-pro"
    openrouter_model_image_gen: str = "google/gemini-2.5-flash-image"
    ai_execution_mode: Literal["api", "runner", "cli", "hybrid"] = "api"
    ai_hybrid_preference: Literal["runner_first", "cli_first", "api_first"] = "runner_first"
    codex_cli_command: str = "codex"
    codex_cli_model: str = ""
    codex_cli_local_provider: Literal["none", "ollama", "lmstudio"] = "none"
    codex_cli_timeout_seconds: int = 180
    codex_cli_max_output_bytes: int = 1_000_000
    codex_cli_ignore_user_config: bool = True
    codex_cli_allow_api_key_env: bool = False
    codex_runner_token: str = ""
    codex_runner_job_ttl_seconds: int = 300
    codex_runner_wait_timeout_seconds: int = 90
    codex_runner_claim_timeout_seconds: int = 15
    codex_runner_heartbeat_ttl_seconds: int = 40
    codex_runner_max_payload_bytes: int = 16_000_000
    product_image_background: Literal["white", "dark"] = "white"
    ai_daily_budget_usd: float = 20

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "ai-wardrobe-private"
    s3_region: str = "us-east-1"
    signed_url_ttl_seconds: int = 900
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_upload_content_types: str = "image/jpeg,image/png,image/webp"
    subscriptions_enabled: bool = True
    enable_billing_payments: bool = False
    enable_marketplace_search: bool = False
    enable_polling_bot: bool = False

    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 30
    rate_limit_uploads_per_minute: int = 60
    rate_limit_ai_per_minute: int = 30

    free_items_limit: int = 20
    free_ai_analyses_per_month: int = 5
    premium_items_limit: int = 500
    premium_ai_analyses_per_month: int = 100
    premium_avatar_generations_per_month: int = 2
    premium_try_ons_per_month: int = 6
    premium_monthly_price_rub: int = 699
    pro_avatar_generations_per_month: int = 5
    pro_try_ons_per_month: int = 15
    pro_monthly_price_rub: int = 1490
    promo_hash_secret: str = ""

    telegram_payment_provider_token: str = ""
    external_payment_provider_url: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def missing_runtime_secrets(self) -> list[str]:
        missing: list[str] = []
        required_fields = ["telegram_bot_token", "jwt_secret_key"]
        if self.ai_execution_mode in {"api", "hybrid"}:
            required_fields.append("openrouter_api_key")
        if self.ai_execution_mode in {"runner", "cli", "hybrid"}:
            required_fields.append("codex_runner_token")
        for field_name in required_fields:
            value = getattr(self, field_name)
            if not value or value == "replace-with-a-long-random-secret":
                missing.append(field_name.upper())
        return missing

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_upload_content_type_set(self) -> set[str]:
        return {content_type.strip() for content_type in self.allowed_upload_content_types.split(",") if content_type}

    def log_file_for(self, service: str) -> str | None:
        return f"{self.log_dir.rstrip('/')}/{service}.log" if self.log_dir else None

    def production_startup_errors(self) -> list[str]:
        if self.app_env != "production":
            return []

        errors: list[str] = []
        default_values = {
            "JWT_SECRET_KEY": self.jwt_secret_key == "replace-with-a-long-random-secret",
            "POSTGRES_PASSWORD": "change-me" in self.database_url or "change-me" in self.sync_database_url,
            "S3_ACCESS_KEY_ID": self.s3_access_key_id == "minioadmin",
            "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key == "minioadmin",
        }
        errors.extend(name for name, is_default in default_values.items() if is_default)

        required = {
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_WEBHOOK_SECRET": self.telegram_webhook_secret,
        }
        if self.ai_execution_mode in {"api", "hybrid"}:
            required["OPENROUTER_API_KEY"] = self.openrouter_api_key
        if self.ai_execution_mode in {"runner", "cli", "hybrid"}:
            required["CODEX_RUNNER_TOKEN"] = self.codex_runner_token
        if self.subscriptions_enabled:
            required["PROMO_HASH_SECRET"] = self.promo_hash_secret
        errors.extend(name for name, value in required.items() if not value)
        if self.ai_execution_mode in {"runner", "cli", "hybrid"} and len(self.codex_runner_token) < 32:
            errors.append("CODEX_RUNNER_TOKEN")
        return sorted(set(errors))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def real_ai_enabled(self) -> bool:
        return self.ai_analysis_enabled

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_analysis_enabled(self) -> bool:
        if self.ai_execution_mode == "api":
            return bool(self.openrouter_api_key)
        if self.ai_execution_mode in {"runner", "cli"}:
            return bool(self.codex_runner_token)
        return bool(self.openrouter_api_key or self.codex_runner_token)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_generation_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_analysis_provider(self) -> str:
        if self.ai_execution_mode == "api":
            return "openrouter" if self.openrouter_api_key else "unconfigured"
        if self.ai_execution_mode in {"runner", "cli"}:
            return "codex_runner" if self.codex_runner_token else "unconfigured"
        preference = "runner_first" if self.ai_hybrid_preference == "cli_first" else self.ai_hybrid_preference
        return f"hybrid:{preference}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_analysis_model(self) -> str:
        if self.ai_execution_mode == "api":
            return self.openrouter_model_image
        if self.ai_execution_mode == "hybrid" and self.ai_hybrid_preference == "api_first":
            return self.openrouter_model_image
        return self.codex_cli_model or "codex-cli-default"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_generation_provider(self) -> str:
        return "openrouter" if self.image_generation_enabled else "unconfigured"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def real_telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

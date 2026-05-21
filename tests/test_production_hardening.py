from uuid import uuid4

import pytest
from aiwardrobe_api.routers.uploads import ensure_user_storage_key, validate_upload_request
from aiwardrobe_core.config import Settings
from fastapi import HTTPException


def test_production_startup_blocks_default_secrets() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="",
        telegram_webhook_secret="",
        jwt_secret_key="replace-with-a-long-random-secret",
        openrouter_api_key="",
        database_url="postgresql+asyncpg://ai_wardrobe:change-me@postgres:5432/ai_wardrobe",
        sync_database_url="postgresql+psycopg://ai_wardrobe:change-me@postgres:5432/ai_wardrobe",
        s3_access_key_id="minioadmin",
        s3_secret_access_key="minioadmin",
    )

    errors = settings.production_startup_errors()

    assert "JWT_SECRET_KEY" in errors
    assert "POSTGRES_PASSWORD" in errors
    assert "S3_SECRET_ACCESS_KEY" in errors
    assert "TELEGRAM_WEBHOOK_SECRET" in errors


def test_production_startup_allows_explicit_runtime_secrets() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="123456:real-token",
        telegram_webhook_secret="webhook-secret",
        jwt_secret_key="a" * 64,
        openrouter_api_key="openrouter-secret",
        database_url="postgresql+asyncpg://user:strong-password@postgres:5432/db",
        sync_database_url="postgresql+psycopg://user:strong-password@postgres:5432/db",
        s3_access_key_id="prod-access-key",
        s3_secret_access_key="prod-secret-key",
    )

    assert settings.production_startup_errors() == []


def test_upload_validation_rejects_spoofed_image_content() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_upload_request("image/jpeg", b"not-a-jpeg", 1024, {"image/jpeg"})

    assert exc_info.value.status_code == 400


def test_upload_validation_accepts_jpeg_magic_bytes() -> None:
    validate_upload_request("image/jpeg", b"\xff\xd8\xffpayload", 1024, {"image/jpeg"})


def test_storage_key_must_belong_to_current_user() -> None:
    user_id = uuid4()
    other_user_id = uuid4()

    ensure_user_storage_key(user_id, f"users/{user_id}/originals/photo.jpg")
    with pytest.raises(HTTPException) as exc_info:
        ensure_user_storage_key(user_id, f"users/{other_user_id}/originals/photo.jpg")

    assert exc_info.value.status_code == 403

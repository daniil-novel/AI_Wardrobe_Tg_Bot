from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from aiwardrobe_core.auth_service import parse_telegram_user
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.llm_gateway import LlmGateway, LlmGatewayError
from aiwardrobe_core.storage import build_storage_key
from aiwardrobe_core.upload_store import UploadStore
from anyio import Path as AsyncPath
from fastapi import UploadFile


def test_parse_telegram_user_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="Telegram user payload is invalid"):
        parse_telegram_user("[1, 2, 3]")


def test_parse_telegram_user_requires_id() -> None:
    with pytest.raises(ValueError, match="Telegram user payload is invalid"):
        parse_telegram_user('{"first_name":"Daniil"}')


def test_build_storage_key_strips_path_components() -> None:
    user_id = UUID("77e6f498-75e1-4f17-8e17-4d0ec870f5e9")

    storage_key = build_storage_key(user_id, "originals", "..\\nested/secret.jpg")

    assert storage_key.startswith(f"users/{user_id}/originals/")
    assert storage_key.endswith("-secret.jpg")
    assert ".." not in Path(storage_key).parts


async def test_upload_store_sanitizes_filename_and_tracks_status(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    upload = UploadFile(filename="..\\unsafe/photo.jpg", file=BytesIO(b"image-bytes"))

    record = await store.save_file(upload, "wardrobe")

    assert record.filename == "..\\unsafe/photo.jpg"
    assert record.storage_key.endswith("photo.jpg")
    assert await AsyncPath(record.storage_key).is_file()

    record.created_at = datetime.now(UTC) - timedelta(seconds=2)
    assert store.get(record.id).status == ProcessingStatus.PROCESSING.value  # type: ignore[union-attr]

    record.created_at = datetime.now(UTC) - timedelta(seconds=5)
    assert store.get(record.id).status == ProcessingStatus.COMPLETED.value  # type: ignore[union-attr]

    old_task_id = record.task_id
    retried = store.retry(record.id)
    assert retried is not None
    assert retried.status == ProcessingStatus.QUEUED.value
    assert retried.task_id != old_task_id
    assert store.delete(record.id) is True
    assert store.get(record.id) is None


def test_upload_store_tracks_telegram_uploads_without_photos_leaking() -> None:
    store = UploadStore()

    record = store.create_telegram_upload("telegram-file-id-with-long-tail", "auto")

    assert record.filename == "telegram-telegram-fil.jpg"
    assert record.content_type == "image/jpeg"
    assert record.storage_key == "telegram/telegram-file-id-with-long-tail"
    assert store.retry(UUID("77e6f498-75e1-4f17-8e17-4d0ec870f5e9")) is None
    assert store.delete(UUID("77e6f498-75e1-4f17-8e17-4d0ec870f5e9")) is False


async def test_llm_gateway_requires_openrouter_key() -> None:
    gateway = LlmGateway(Settings(openrouter_api_key=""))

    with pytest.raises(LlmGatewayError, match="OPENROUTER_API_KEY"):
        await gateway.generate_text_json("{}", "schema")


async def test_llm_gateway_validates_text_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
            request = httpx.Request("POST", "https://openrouter.test/chat/completions")
            return httpx.Response(
                200,
                request=request,
                json={"choices": [{"message": {"content": '{"title":"Office capsule","score":0.91}'}}]},
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test", public_api_url="https://example.test"))

    assert await gateway.generate_text_json("prompt", "OutfitResearch") == {
        "title": "Office capsule",
        "score": 0.91,
    }


async def test_llm_gateway_rejects_non_object_text_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
            request = httpx.Request("POST", "https://openrouter.test/chat/completions")
            return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "[1, 2, 3]"}}]})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test"))

    with pytest.raises(LlmGatewayError, match="not a JSON object"):
        await gateway.generate_text_json("prompt", "OutfitResearch")

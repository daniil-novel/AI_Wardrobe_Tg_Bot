from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import ProcessingStatus, UploadSource
from aiwardrobe_core.image_validation import ImageValidationError, validate_image_content
from aiwardrobe_core.models import Upload
from aiwardrobe_worker.tasks import transfer_telegram_upload

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"0" * 32
ALLOWED = {"image/jpeg", "image/png", "image/webp"}


def test_validate_image_content_detects_supported_formats() -> None:
    assert validate_image_content(JPEG_BYTES, 1024, ALLOWED) == "image/jpeg"
    assert validate_image_content(PNG_BYTES, 1024, ALLOWED) == "image/png"
    assert validate_image_content(WEBP_BYTES, 1024, ALLOWED) == "image/webp"


def test_validate_image_content_rejects_non_image() -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_content(b"GIF89a" + b"0" * 32, 1024, ALLOWED)
    assert excinfo.value.code == "invalid_image"


def test_validate_image_content_rejects_oversized_payload() -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_content(JPEG_BYTES, 8, ALLOWED)
    assert excinfo.value.code == "file_too_large"


def test_validate_image_content_rejects_disallowed_type() -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        validate_image_content(PNG_BYTES, 1024, {"image/jpeg"})
    assert excinfo.value.code == "unsupported_content_type"


def test_transfer_task_fails_closed_without_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: Settings(telegram_bot_token=""))

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        transfer_telegram_upload.run(str(uuid4()))


class FakeResult:
    def __init__(self, upload: Upload | None) -> None:
        self.upload = upload

    def scalar_one_or_none(self) -> Upload | None:
        return self.upload


class FakeSession:
    def __init__(self, upload: Upload | None) -> None:
        self.upload = upload
        self.added: list[Any] = []
        self.commits = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, _query: Any) -> FakeResult:
        return FakeResult(self.upload)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self) -> None:
        self.commits += 1


class FakeResponse:
    def __init__(self, json_data: dict[str, Any] | None = None, content: bytes = b"") -> None:
        self._json = json_data or {}
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._json


class FakeHttpClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeHttpClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        if url.endswith("/getFile"):
            return FakeResponse(json_data={"result": {"file_path": "photos/file_1.jpg"}})
        return FakeResponse(content=JPEG_BYTES)


class FakeTask:
    def __init__(self) -> None:
        self.id = str(uuid4())


def make_telegram_upload() -> Upload:
    return Upload(
        id=uuid4(),
        user_id=uuid4(),
        source=UploadSource.TELEGRAM.value,
        upload_type="auto",
        telegram_file_id="AgACAgIAAxkBAAI",
        status=ProcessingStatus.CREATED.value,
    )


def test_transfer_task_moves_telegram_file_to_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_telegram_upload()
    session = FakeSession(upload)
    stored: dict[str, Any] = {}

    async def fake_put_bytes(self: Any, storage_key: str, content: bytes, content_type: str) -> None:
        stored["key"] = storage_key
        stored["content_type"] = content_type

    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: Settings(telegram_bot_token="123:abc"))
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_session_factory", lambda: lambda: session)
    monkeypatch.setattr("aiwardrobe_worker.tasks.httpx.AsyncClient", FakeHttpClient)
    monkeypatch.setattr("aiwardrobe_core.storage.ObjectStorage.put_bytes", fake_put_bytes)
    monkeypatch.setattr("aiwardrobe_worker.tasks.analyze_upload.delay", lambda *args: FakeTask())

    result = transfer_telegram_upload.run(str(upload.id))

    assert result["status"] == ProcessingStatus.QUEUED.value
    assert upload.original_image_id is not None
    assert upload.task_id is not None
    assert stored["key"].startswith(f"users/{upload.user_id}/originals/")
    assert stored["content_type"] == "image/jpeg"


def test_transfer_task_skips_already_transferred_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_telegram_upload()
    upload.original_image_id = uuid4()
    upload.status = ProcessingStatus.COMPLETED.value
    session = FakeSession(upload)

    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: Settings(telegram_bot_token="123:abc"))
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_session_factory", lambda: lambda: session)

    result = transfer_telegram_upload.run(str(upload.id))

    assert result["skipped"] == "already_transferred"
    assert session.commits == 0


def test_telegram_uploads_are_enqueued_not_left_pending() -> None:
    uploads_router = Path("apps/api/aiwardrobe_api/routers/uploads.py").read_text(encoding="utf-8")

    assert "telegram_transfer_pending" not in uploads_router
    assert "enqueue_telegram_transfer" in uploads_router
    assert "transfer_telegram_upload" in uploads_router


def test_upload_retry_re_enqueues_real_tasks() -> None:
    uploads_router = Path("apps/api/aiwardrobe_api/routers/uploads.py").read_text(encoding="utf-8")
    ai_router = Path("apps/api/aiwardrobe_api/routers/ai.py").read_text(encoding="utf-8")

    assert "task_id = str(uuid4())" not in uploads_router
    assert uploads_router.count("enqueue_upload_with_key") >= 3
    assert "analyze_upload.delay" in ai_router


def test_worker_generates_presigned_url_from_storage_key() -> None:
    tasks_file = Path("apps/worker/aiwardrobe_worker/tasks.py").read_text(encoding="utf-8")

    assert "create_presigned_get_url" in tasks_file
    assert "def analyze_upload(self: Any, upload_id: str, storage_key: str)" in tasks_file


def test_worker_compose_listens_on_all_task_queues() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    compose_prod = Path("docker-compose.prod.yml").read_text(encoding="utf-8")

    for text in (compose, compose_prod):
        assert "-Q celery,ai,research,recommendations,notifications" in text


def test_bot_webhook_mode_does_not_nest_event_loops() -> None:
    bot_main = Path("apps/bot/aiwardrobe_bot/main.py").read_text(encoding="utf-8")

    assert "web.run_app" not in bot_main
    assert "web.AppRunner" in bot_main
    assert 'rstrip("/")' in bot_main

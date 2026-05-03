from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from aiwardrobe_core.enums import ProcessingStatus


@dataclass
class UploadRecord:
    id: UUID
    filename: str
    content_type: str
    upload_type: str
    storage_key: str
    status: str = ProcessingStatus.QUEUED.value
    task_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_code: str | None = None
    error_message: str | None = None


class UploadStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path("storage/uploads")
        self.records: dict[UUID, UploadRecord] = {}

    async def save_file(self, file: UploadFile, upload_type: str) -> UploadRecord:
        upload_id = uuid4()
        safe_name = file.filename or "upload.jpg"
        clean_name = safe_name.replace("\\", "/").split("/")[-1]
        storage_key = f"{upload_id}/{clean_name}"
        target = self.base_dir / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        target.write_bytes(content)
        record = UploadRecord(
            id=upload_id,
            filename=safe_name,
            content_type=file.content_type or "application/octet-stream",
            upload_type=upload_type,
            storage_key=str(target),
        )
        self.records[upload_id] = record
        return record

    def create_telegram_upload(self, telegram_file_id: str, upload_type: str) -> UploadRecord:
        upload_id = uuid4()
        record = UploadRecord(
            id=upload_id,
            filename=f"telegram-{telegram_file_id[:12]}.jpg",
            content_type="image/jpeg",
            upload_type=upload_type,
            storage_key=f"telegram/{telegram_file_id}",
        )
        self.records[upload_id] = record
        return record

    def get(self, upload_id: UUID) -> UploadRecord | None:
        record = self.records.get(upload_id)
        if record is None:
            return None
        elapsed = (datetime.now(UTC) - record.created_at).total_seconds()
        if elapsed >= 4:
            record.status = ProcessingStatus.COMPLETED.value
        elif elapsed >= 1:
            record.status = ProcessingStatus.PROCESSING.value
        return record

    def retry(self, upload_id: UUID) -> UploadRecord | None:
        record = self.records.get(upload_id)
        if record is None:
            return None
        record.status = ProcessingStatus.QUEUED.value
        record.created_at = datetime.now(UTC)
        record.task_id = str(uuid4())
        return record

    def delete(self, upload_id: UUID) -> bool:
        return self.records.pop(upload_id, None) is not None


upload_store = UploadStore()

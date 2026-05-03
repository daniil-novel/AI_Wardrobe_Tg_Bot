from typing import Annotated
from uuid import UUID, uuid4

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.schemas import (
    TelegramUploadRequest,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadStatus,
)
from aiwardrobe_core.storage import ObjectStorage, build_storage_key
from aiwardrobe_core.upload_store import UploadRecord, upload_store
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

router = APIRouter(prefix="/uploads", tags=["uploads"])


def status_from_record(record: UploadRecord) -> UploadStatus:
    progress_by_status = {
        ProcessingStatus.QUEUED.value: 25,
        ProcessingStatus.PROCESSING.value: 70,
        ProcessingStatus.COMPLETED.value: 100,
        ProcessingStatus.FAILED.value: 0,
    }
    return UploadStatus(
        id=record.id,
        status=record.status,
        task_id=record.task_id,
        error_code=record.error_code,
        error_message=record.error_message,
        filename=record.filename,
        upload_type=record.upload_type,
        progress=progress_by_status.get(record.status, 10),
        result_title="Карточка готова" if record.status == ProcessingStatus.COMPLETED.value else None,
    )


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(payload: UploadInitRequest) -> UploadInitResponse:
    settings = get_settings()
    upload_id = uuid4()
    user_id = uuid4()
    storage_key = build_storage_key(user_id, "originals", payload.filename)
    signed_url = await ObjectStorage(settings).create_presigned_put_url(storage_key, payload.content_type)
    return UploadInitResponse(
        upload_id=upload_id,
        storage_key=storage_key,
        signed_url=signed_url,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )


@router.post("/complete", response_model=UploadStatus)
async def complete_upload(payload: UploadCompleteRequest, background: BackgroundTasks) -> UploadStatus:
    task_id = str(uuid4())
    background.add_task(lambda: None)
    return UploadStatus(id=payload.upload_id, status=ProcessingStatus.QUEUED.value, task_id=task_id)


@router.post("/file", response_model=UploadStatus)
async def upload_file(file: Annotated[UploadFile, File()], upload_type: str = "auto") -> UploadStatus:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are supported.")
    record = await upload_store.save_file(file, upload_type)
    return status_from_record(record)


@router.post("/from-telegram", response_model=UploadStatus)
async def from_telegram(payload: TelegramUploadRequest) -> UploadStatus:
    if not payload.telegram_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="telegram_file_id is required.")
    record = upload_store.create_telegram_upload(payload.telegram_file_id, payload.upload_type)
    return status_from_record(record)


@router.get("/{upload_id}", response_model=UploadStatus)
async def get_upload(upload_id: UUID) -> UploadStatus:
    record = upload_store.get(upload_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return status_from_record(record)


@router.post("/{upload_id}/retry", response_model=UploadStatus)
async def retry_upload(upload_id: UUID) -> UploadStatus:
    record = upload_store.retry(upload_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return status_from_record(record)


@router.delete("/{upload_id}")
async def delete_upload(upload_id: UUID) -> dict[str, UUID | str]:
    upload_store.delete(upload_id)
    return {"id": upload_id, "status": "deleted"}

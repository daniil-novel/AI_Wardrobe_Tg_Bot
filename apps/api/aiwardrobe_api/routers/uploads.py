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
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

router = APIRouter(prefix="/uploads", tags=["uploads"])


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


@router.post("/from-telegram", response_model=UploadStatus)
async def from_telegram(payload: TelegramUploadRequest) -> UploadStatus:
    if not payload.telegram_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="telegram_file_id is required.")
    return UploadStatus(id=uuid4(), status=ProcessingStatus.QUEUED.value, task_id=str(uuid4()))


@router.get("/{upload_id}", response_model=UploadStatus)
async def get_upload(upload_id: UUID) -> UploadStatus:
    return UploadStatus(id=upload_id, status=ProcessingStatus.PROCESSING.value)


@router.post("/{upload_id}/retry", response_model=UploadStatus)
async def retry_upload(upload_id: UUID) -> UploadStatus:
    return UploadStatus(id=upload_id, status=ProcessingStatus.QUEUED.value, task_id=str(uuid4()))


@router.delete("/{upload_id}")
async def delete_upload(upload_id: UUID) -> dict[str, UUID | str]:
    return {"id": upload_id, "status": "deleted"}

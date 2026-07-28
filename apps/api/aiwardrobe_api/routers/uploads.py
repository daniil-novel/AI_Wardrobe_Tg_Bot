import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from aiwardrobe_core.auth_service import upsert_telegram_user
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.enums import ProcessingStatus, ProvenanceLabel, UploadSource
from aiwardrobe_core.image_validation import ImageValidationError, validate_image_content
from aiwardrobe_core.models import ImageAsset, ImageSelection, Upload
from aiwardrobe_core.schemas import (
    TelegramUploadRequest,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadSelectionPayload,
    UploadStatus,
)
from aiwardrobe_core.storage import ObjectStorage, build_storage_key
from aiwardrobe_core.usage import UsageQuotaExceeded, reserve_billable_request
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/uploads", tags=["uploads"])


def status_from_upload(upload: Upload) -> UploadStatus:
    progress_by_status = {
        ProcessingStatus.CREATED.value: 10,
        ProcessingStatus.UPLOADED.value: 20,
        ProcessingStatus.QUEUED.value: 25,
        ProcessingStatus.PROCESSING.value: 70,
        ProcessingStatus.COMPLETED.value: 100,
        ProcessingStatus.FAILED.value: 0,
    }
    return UploadStatus(
        id=upload.id,
        status=upload.status,
        task_id=upload.task_id,
        error_code=upload.error_code,
        error_message=upload.error_message,
        filename=upload.telegram_file_id,
        upload_type=upload.upload_type,
        progress=progress_by_status.get(upload.status, 10),
        result_title="Карточка готова" if upload.status == ProcessingStatus.COMPLETED.value else None,
    )


def validate_upload_request(content_type: str, content: bytes, max_bytes: int, allowed_types: set[str]) -> None:
    if content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image content type.")
    try:
        validate_image_content(content, max_bytes, allowed_types)
    except ImageValidationError as exc:
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if exc.code == "file_too_large" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=exc.message) from exc


def ensure_user_storage_key(user_id: UUID, storage_key: str) -> None:
    if not storage_key.startswith(f"users/{user_id}/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Storage key does not belong to user.")


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    payload: UploadInitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> UploadInitResponse:
    settings = get_settings()
    if payload.content_type not in settings.allowed_upload_content_type_set:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image content type.")
    upload_id = uuid4()
    storage_key = build_storage_key(user_id, "originals", payload.filename)
    signed_url = await ObjectStorage(settings).create_presigned_put_url(storage_key, payload.content_type)
    upload = Upload(
        id=upload_id,
        user_id=user_id,
        source=UploadSource.MINIAPP.value,
        upload_type=payload.upload_type,
        status=ProcessingStatus.CREATED.value,
    )
    session.add(upload)
    await session.commit()
    return UploadInitResponse(
        upload_id=upload.id,
        storage_key=storage_key,
        signed_url=signed_url,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )


@router.post("/complete", response_model=UploadStatus)
async def complete_upload(
    payload: UploadCompleteRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> UploadStatus:
    ensure_user_storage_key(user_id, payload.storage_key)
    upload = await load_upload(session, user_id, payload.upload_id)
    if upload.task_id and upload.status in {ProcessingStatus.QUEUED.value, ProcessingStatus.PROCESSING.value}:
        return status_from_upload(upload)

    settings = get_settings()
    storage = ObjectStorage(settings)
    if not await storage.object_exists(payload.storage_key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uploaded object is not present in storage.")
    image = ImageAsset(
        user_id=user_id,
        source_type="upload",
        storage_key=payload.storage_key,
        provenance_label=ProvenanceLabel.USER_PROCESSED.value,
    )
    session.add(image)
    await session.flush()
    upload.original_image_id = image.id
    upload.status = ProcessingStatus.UPLOADED.value
    await enqueue_upload_with_key(session, upload, payload.storage_key)
    await session.commit()
    await session.refresh(upload)
    return status_from_upload(upload)


@router.post("/file", response_model=UploadStatus)
async def upload_file(
    file: Annotated[UploadFile, File()],
    selection_json: Annotated[str | None, Form()] = None,
    upload_type: str = "auto",
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> UploadStatus:
    settings = get_settings()
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    validate_upload_request(content_type, content, settings.max_upload_bytes, settings.allowed_upload_content_type_set)
    storage_key = build_storage_key(user_id, "originals", file.filename or "upload")
    storage = ObjectStorage(settings)
    await storage.put_bytes(storage_key, content, content_type)
    image = ImageAsset(
        user_id=user_id,
        source_type="upload",
        storage_key=storage_key,
        provenance_label=ProvenanceLabel.USER_PROCESSED.value,
    )
    session.add(image)
    await session.flush()
    upload = Upload(
        user_id=user_id,
        source=UploadSource.MINIAPP.value,
        upload_type=upload_type,
        status=ProcessingStatus.UPLOADED.value,
        original_image_id=image.id,
    )
    session.add(upload)
    await session.flush()
    if selection_json:
        try:
            selection = UploadSelectionPayload.model_validate(json.loads(selection_json))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid image selection metadata.",
            ) from exc
        session.add(
            ImageSelection(
                upload_id=upload.id,
                user_id=user_id,
                kind=selection.kind,
                source=selection.source,
                geometry={
                    "x": selection.x,
                    "y": selection.y,
                    "width": selection.width,
                    "height": selection.height,
                },
            )
        )
    await enqueue_upload_with_key(session, upload, storage_key)
    await session.commit()
    await session.refresh(upload)
    return status_from_upload(upload)


@router.post("/from-telegram", response_model=UploadStatus)
async def from_telegram(
    payload: TelegramUploadRequest,
    x_telegram_webhook_secret: str | None = Header(default=None),
    session: AsyncSession = DbSession,
) -> UploadStatus:
    settings = get_settings()
    if not settings.telegram_webhook_secret or x_telegram_webhook_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram webhook secret.")
    user = await upsert_telegram_user(
        session,
        {
            "id": payload.telegram_id,
            "username": payload.telegram_username,
            "first_name": payload.first_name,
            "language_code": payload.language,
        },
    )
    upload = Upload(
        user_id=user.id,
        source=UploadSource.TELEGRAM.value,
        upload_type=payload.upload_type,
        telegram_file_id=payload.telegram_file_id,
        status=ProcessingStatus.CREATED.value,
    )
    session.add(upload)
    await session.flush()
    await enqueue_telegram_transfer(upload)
    await session.commit()
    await session.refresh(upload)
    return status_from_upload(upload)


@router.get("/{upload_id}", response_model=UploadStatus)
async def get_upload(upload_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> UploadStatus:
    return status_from_upload(await load_upload(session, user_id, upload_id))


@router.post("/{upload_id}/retry", response_model=UploadStatus)
async def retry_upload(upload_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> UploadStatus:
    upload = await load_upload(session, user_id, upload_id)
    if upload.original_image_id is None:
        if upload.telegram_file_id:
            upload.error_code = None
            upload.error_message = None
            await enqueue_telegram_transfer(upload)
            await session.commit()
            await session.refresh(upload)
            return status_from_upload(upload)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload has no stored image to retry.")
    image = await session.get(ImageAsset, upload.original_image_id)
    if image is None or image.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload image is no longer available.")
    upload.error_code = None
    upload.error_message = None
    await enqueue_upload_with_key(session, upload, image.storage_key)
    await session.commit()
    await session.refresh(upload)
    return status_from_upload(upload)


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    upload = await load_upload(session, user_id, upload_id)
    upload.status = ProcessingStatus.CANCELLED.value
    upload.completed_at = datetime.now(UTC)
    await session.commit()
    return {"id": upload_id, "status": "deleted"}


async def enqueue_upload_with_key(session: AsyncSession, upload: Upload, storage_key: str) -> None:
    settings = get_settings()
    try:
        usage_request = await reserve_billable_request(
            session,
            upload.user_id,
            upload.id,
            "analyze_image",
            settings.ai_analysis_model,
            provider=settings.ai_analysis_provider,
            settings=settings,
        )
    except UsageQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly AI analysis quota exceeded.",
        ) from exc
    try:
        from aiwardrobe_worker.tasks import analyze_upload

        task = analyze_upload.delay(str(upload.id), storage_key)
    except Exception as exc:
        upload.status = ProcessingStatus.FAILED.value
        upload.error_code = "queue_unavailable"
        upload.error_message = exc.__class__.__name__
        usage_request.status = ProcessingStatus.FAILED.value
        usage_request.error_code = "queue_unavailable"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc
    upload.task_id = str(task.id)
    upload.status = ProcessingStatus.QUEUED.value


async def enqueue_telegram_transfer(upload: Upload) -> None:
    try:
        from aiwardrobe_worker.tasks import transfer_telegram_upload

        task = transfer_telegram_upload.delay(str(upload.id))
    except Exception as exc:
        upload.status = ProcessingStatus.FAILED.value
        upload.error_code = "queue_unavailable"
        upload.error_message = exc.__class__.__name__
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc
    upload.task_id = str(task.id)
    upload.status = ProcessingStatus.QUEUED.value


async def load_upload(session: AsyncSession, user_id: UUID, upload_id: UUID) -> Upload:
    result = await session.execute(select(Upload).where(Upload.id == upload_id, Upload.user_id == user_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return upload

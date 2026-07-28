from datetime import UTC, datetime, timedelta
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.models import AiRequest, ImageAsset, Upload
from aiwardrobe_core.schemas import AiTaskRequest, AiTaskStatus
from aiwardrobe_core.usage import UsageQuotaExceeded, reserve_billable_request
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-image", response_model=AiTaskStatus)
async def analyze_image(
    payload: AiTaskRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> AiTaskStatus:
    settings = get_settings()
    if not settings.ai_analysis_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No real AI analysis provider is configured; mock AI mode is intentionally disabled.",
        )
    upload = await load_upload(session, user_id, payload.upload_id)
    if upload.original_image_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload has no stored image.")
    if upload.task_id and upload.status in {ProcessingStatus.QUEUED.value, ProcessingStatus.PROCESSING.value}:
        return AiTaskStatus(task_id=upload.task_id, status=upload.status)

    try:
        usage_request = await reserve_billable_request(
            session,
            user_id,
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
    image = await load_image(session, user_id, upload.original_image_id)
    try:
        from aiwardrobe_worker.tasks import analyze_upload

        task = analyze_upload.delay(str(upload.id), image.storage_key)
    except Exception as exc:
        upload.status = ProcessingStatus.FAILED.value
        upload.error_code = "queue_unavailable"
        upload.error_message = exc.__class__.__name__
        usage_request.status = ProcessingStatus.FAILED.value
        usage_request.error_code = "queue_unavailable"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc

    upload.status = ProcessingStatus.QUEUED.value
    upload.task_id = str(task.id)
    await session.commit()
    return AiTaskStatus(task_id=upload.task_id, status=upload.status)


@router.get("/tasks/{task_id}", response_model=AiTaskStatus)
async def get_task(task_id: str, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> AiTaskStatus:
    result = await session.execute(select(Upload).where(Upload.task_id == task_id, Upload.user_id == user_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return AiTaskStatus(task_id=task_id, status=upload.status)


@router.post("/tasks/{task_id}/retry", response_model=AiTaskStatus)
async def retry_task(task_id: str, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> AiTaskStatus:
    result = await session.execute(select(Upload).where(Upload.task_id == task_id, Upload.user_id == user_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if upload.original_image_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload has no stored image to retry.")
    settings = get_settings()
    try:
        usage_request = await reserve_billable_request(
            session,
            user_id,
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
    image = await load_image(session, user_id, upload.original_image_id)
    try:
        from aiwardrobe_worker.tasks import analyze_upload

        task = analyze_upload.delay(str(upload.id), image.storage_key)
    except Exception as exc:
        usage_request.status = ProcessingStatus.FAILED.value
        usage_request.error_code = "queue_unavailable"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc
    upload.status = ProcessingStatus.QUEUED.value
    upload.error_code = None
    upload.error_message = None
    upload.task_id = str(task.id)
    await session.commit()
    return AiTaskStatus(task_id=upload.task_id, status=upload.status)


@router.get("/usage")
async def usage(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> dict[str, int | float]:
    since = datetime.now(UTC) - timedelta(days=1)
    result = await session.execute(
        select(func.count(AiRequest.id), func.coalesce(func.sum(AiRequest.cost_usd), 0)).where(
            AiRequest.user_id == user_id, AiRequest.created_at >= since
        )
    )
    requests_today, cost_today = result.one()
    return {"requests_today": int(requests_today), "cost_usd_today": float(cost_today)}


async def load_upload(session: AsyncSession, user_id: UUID, upload_id: UUID) -> Upload:
    result = await session.execute(select(Upload).where(Upload.id == upload_id, Upload.user_id == user_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return upload


async def load_image(session: AsyncSession, user_id: UUID, image_id: UUID) -> ImageAsset:
    result = await session.execute(select(ImageAsset).where(ImageAsset.id == image_id, ImageAsset.user_id == user_id))
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return image

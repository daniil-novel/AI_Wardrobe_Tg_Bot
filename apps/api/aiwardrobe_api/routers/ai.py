from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.models import AiRequest, ImageAsset, Upload, User
from aiwardrobe_core.schemas import AiTaskRequest, AiTaskStatus
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
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENROUTER_API_KEY is required; mock AI mode is intentionally disabled.",
        )
    upload = await load_upload(session, user_id, payload.upload_id)
    if upload.original_image_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload has no stored image.")
    if upload.task_id and upload.status in {ProcessingStatus.QUEUED.value, ProcessingStatus.PROCESSING.value}:
        return AiTaskStatus(task_id=upload.task_id, status=upload.status)

    await enforce_ai_quota(session, user_id)
    image = await load_image(session, user_id, upload.original_image_id)
    try:
        from aiwardrobe_worker.tasks import analyze_upload

        task = analyze_upload.delay(str(upload.id), image.storage_key)
    except Exception as exc:
        upload.status = ProcessingStatus.FAILED.value
        upload.error_code = "queue_unavailable"
        upload.error_message = exc.__class__.__name__
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc

    upload.status = ProcessingStatus.QUEUED.value
    upload.task_id = str(task.id)
    session.add(
        AiRequest(
            user_id=user_id,
            task_id=upload.id,
            model=settings.openrouter_model_image,
            request_type=payload.task_type,
            status=ProcessingStatus.QUEUED.value,
            cost_usd=Decimal("0"),
        )
    )
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
    await enforce_ai_quota(session, user_id)
    image = await load_image(session, user_id, upload.original_image_id)
    try:
        from aiwardrobe_worker.tasks import analyze_upload

        task = analyze_upload.delay(str(upload.id), image.storage_key)
    except Exception as exc:
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


async def enforce_ai_quota(session: AsyncSession, user_id: UUID) -> None:
    settings = get_settings()
    user = await session.get(User, user_id)
    limit = settings.free_ai_analyses_per_month
    if user and user.subscription_plan in {"premium", "pro"}:
        limit = settings.premium_ai_analyses_per_month if user.subscription_plan == "premium" else 10**9
    since = datetime.now(UTC) - timedelta(days=30)
    used = await session.scalar(
        select(func.count(AiRequest.id)).where(AiRequest.user_id == user_id, AiRequest.created_at >= since)
    )
    if int(used or 0) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly AI analysis quota exceeded.")


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

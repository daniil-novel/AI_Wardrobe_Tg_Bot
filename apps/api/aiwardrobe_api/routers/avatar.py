from datetime import UTC, datetime
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.entitlements import resolve_effective_access
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.models import (
    AvatarMeasurement,
    AvatarProfile,
    GarmentItem,
    ImageAsset,
    TryOnItem,
    TryOnJob,
    Upload,
)
from aiwardrobe_core.schemas import (
    AvatarMeasurementRead,
    AvatarProfileRead,
    AvatarProfileUpdate,
    TryOnCreate,
    TryOnRead,
)
from aiwardrobe_core.storage import ObjectStorage
from aiwardrobe_core.usage import UsageQuotaExceeded, reserve_billable_request
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/avatar", tags=["avatar"])


async def _load_profile(session: AsyncSession, user_id: UUID) -> AvatarProfile:
    result = await session.execute(select(AvatarProfile).where(AvatarProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar profile not found.")
    return profile


async def _profile_read(session: AsyncSession, profile: AvatarProfile) -> AvatarProfileRead:
    result = await session.execute(
        select(AvatarMeasurement)
        .where(AvatarMeasurement.avatar_profile_id == profile.id)
        .order_by(AvatarMeasurement.code)
    )
    measurements = list(result.scalars())
    return AvatarProfileRead(
        id=profile.id,
        status=profile.status,
        description=profile.description,
        neutral_clothing=profile.neutral_clothing,
        reference_image_id=profile.reference_image_id,
        generated_image_id=profile.generated_image_id,
        consent_version=profile.consent_version,
        consented_at=profile.consented_at,
        revoked_at=profile.revoked_at,
        generation_error=profile.generation_error,
        generated_at=profile.generated_at,
        measurements=[
            AvatarMeasurementRead(
                code=measurement.code,
                value=measurement.value,
                unit=measurement.unit,
                source=measurement.source,
                confidence=measurement.confidence,
            )
            for measurement in measurements
        ],
    )


async def _require_avatar_access(session: AsyncSession, user_id: UUID) -> None:
    if not get_settings().subscriptions_enabled:
        return
    access = await resolve_effective_access(session, user_id)
    if "avatar_try_on" not in access.features:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium access is required for avatar generation and virtual try-on.",
        )


@router.get("/profile", response_model=AvatarProfileRead | None)
async def get_avatar_profile(
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> AvatarProfileRead | None:
    result = await session.execute(select(AvatarProfile).where(AvatarProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    return await _profile_read(session, profile) if profile is not None else None


@router.put("/profile", response_model=AvatarProfileRead)
async def update_avatar_profile(
    payload: AvatarProfileUpdate,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> AvatarProfileRead:
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Explicit avatar processing consent is required. Use DELETE to revoke existing consent.",
        )
    await _require_avatar_access(session, user_id)
    reference_image_id: UUID | None = None
    if payload.reference_upload_id:
        upload_result = await session.execute(
            select(Upload).where(Upload.id == payload.reference_upload_id, Upload.user_id == user_id)
        )
        upload = upload_result.scalar_one_or_none()
        if upload is None or upload.original_image_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference upload not found.")
        reference_image_id = upload.original_image_id

    profile_result = await session.execute(select(AvatarProfile).where(AvatarProfile.user_id == user_id))
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        profile = AvatarProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
    profile.status = "ready_for_generation" if reference_image_id or profile.reference_image_id else "draft"
    profile.description = payload.description
    profile.neutral_clothing = payload.neutral_clothing
    profile.reference_image_id = reference_image_id or profile.reference_image_id
    profile.consent_version = payload.consent_version
    profile.consented_at = datetime.now(UTC)
    profile.revoked_at = None
    profile.generation_error = None

    await session.execute(delete(AvatarMeasurement).where(AvatarMeasurement.avatar_profile_id == profile.id))
    session.add_all(
        [
            AvatarMeasurement(
                avatar_profile_id=profile.id,
                code=measurement.code,
                value=measurement.value,
                unit=measurement.unit,
                source="user",
            )
            for measurement in payload.measurements
        ]
    )
    await session.commit()
    await session.refresh(profile)
    return await _profile_read(session, profile)


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_avatar_profile(
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> Response:
    profile = await _load_profile(session, user_id)
    output_result = await session.execute(
        select(TryOnJob.output_image_id).where(
            TryOnJob.avatar_profile_id == profile.id,
            TryOnJob.output_image_id.is_not(None),
        )
    )
    derived_image_ids = {
        image_id for image_id in [profile.generated_image_id, *output_result.scalars()] if image_id is not None
    }
    if derived_image_ids:
        image_result = await session.execute(
            select(ImageAsset).where(
                ImageAsset.id.in_(derived_image_ids),
                ImageAsset.user_id == user_id,
            )
        )
        storage = ObjectStorage(get_settings())
        try:
            for image in image_result.scalars():
                await storage.delete_object(image.storage_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Avatar data cleanup is temporarily unavailable. Retry revocation.",
            ) from exc

    profile.status = "revoked"
    profile.description = None
    profile.reference_image_id = None
    profile.generated_image_id = None
    profile.consent_version = None
    profile.consented_at = None
    profile.revoked_at = datetime.now(UTC)
    profile.generation_error = None
    await session.execute(delete(TryOnJob).where(TryOnJob.avatar_profile_id == profile.id))
    await session.execute(delete(AvatarMeasurement).where(AvatarMeasurement.avatar_profile_id == profile.id))
    if derived_image_ids:
        await session.execute(delete(ImageAsset).where(ImageAsset.id.in_(derived_image_ids)))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/generate", response_model=AvatarProfileRead, status_code=status.HTTP_202_ACCEPTED)
async def generate_avatar(
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> AvatarProfileRead:
    await _require_avatar_access(session, user_id)
    profile = await _load_profile(session, user_id)
    if profile.consented_at is None or profile.revoked_at is not None or profile.reference_image_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Save a consented avatar profile with a reference upload first.",
        )
    if profile.status in {ProcessingStatus.QUEUED.value, ProcessingStatus.PROCESSING.value}:
        return await _profile_read(session, profile)
    settings = get_settings()
    if not settings.image_generation_enabled:
        profile.status = ProcessingStatus.FAILED.value
        profile.generation_error = "provider_not_configured"
        await session.commit()
        return await _profile_read(session, profile)
    try:
        usage_request = await reserve_billable_request(
            session,
            user_id,
            profile.id,
            "generate_avatar",
            settings.openrouter_model_image_gen,
            settings=settings,
            idempotent=False,
        )
    except UsageQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly avatar generation quota exceeded.",
        ) from exc
    try:
        from aiwardrobe_worker.tasks import generate_avatar_image

        generate_avatar_image.delay(str(profile.id))
    except Exception as exc:
        usage_request.status = ProcessingStatus.FAILED.value
        usage_request.error_code = "queue_unavailable"
        profile.status = ProcessingStatus.FAILED.value
        profile.generation_error = "queue_unavailable"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable.") from exc
    profile.status = ProcessingStatus.QUEUED.value
    profile.generation_error = None
    await session.commit()
    return await _profile_read(session, profile)


@router.get("/image")
async def get_avatar_image(
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> Response:
    profile = await _load_profile(session, user_id)
    if profile.generated_image_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar image not found.")
    image = await session.get(ImageAsset, profile.generated_image_id)
    if image is None or image.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar image not found.")
    content = await ObjectStorage(get_settings()).get_bytes(image.storage_key)
    return Response(content=content, media_type="image/png")


async def _try_on_read(session: AsyncSession, job: TryOnJob) -> TryOnRead:
    item_result = await session.execute(
        select(TryOnItem).where(TryOnItem.try_on_job_id == job.id).order_by(TryOnItem.sort_order)
    )
    return TryOnRead(
        id=job.id,
        status=job.status,
        provider=job.provider,
        output_image_id=job.output_image_id,
        error_code=job.error_code,
        error_message=job.error_message,
        garment_item_ids=[item.item_id for item in item_result.scalars()],
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.post("/try-ons", response_model=TryOnRead, status_code=status.HTTP_202_ACCEPTED)
async def create_try_on(
    payload: TryOnCreate,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> TryOnRead:
    await _require_avatar_access(session, user_id)
    profile = await _load_profile(session, user_id)
    if profile.generated_image_id is None or profile.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate the avatar before virtual try-on.")
    item_result = await session.execute(
        select(GarmentItem).where(
            GarmentItem.id.in_(payload.garment_item_ids),
            GarmentItem.user_id == user_id,
            GarmentItem.deleted_at.is_(None),
        )
    )
    items = list(item_result.scalars())
    if len(items) != len(set(payload.garment_item_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more garments were not found.")
    settings = get_settings()
    job = TryOnJob(
        user_id=user_id,
        avatar_profile_id=profile.id,
        status=ProcessingStatus.CREATED.value,
        provider=settings.image_generation_provider if settings.image_generation_enabled else None,
    )
    session.add(job)
    await session.flush()
    session.add_all(
        [
            TryOnItem(try_on_job_id=job.id, item_id=item_id, sort_order=index)
            for index, item_id in enumerate(payload.garment_item_ids)
        ]
    )
    if not settings.image_generation_enabled:
        job.status = ProcessingStatus.FAILED.value
        job.error_code = "provider_not_configured"
        job.error_message = "Image generation provider is not configured."
        job.completed_at = datetime.now(UTC)
    else:
        try:
            usage_request = await reserve_billable_request(
                session,
                user_id,
                job.id,
                "virtual_try_on",
                settings.openrouter_model_image_gen,
                settings=settings,
            )
        except UsageQuotaExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Monthly virtual try-on quota exceeded.",
            ) from exc
        try:
            from aiwardrobe_worker.tasks import generate_virtual_try_on

            task = generate_virtual_try_on.delay(str(job.id))
        except Exception as exc:
            usage_request.status = ProcessingStatus.FAILED.value
            usage_request.error_code = "queue_unavailable"
            job.status = ProcessingStatus.FAILED.value
            job.error_code = "queue_unavailable"
            job.error_message = "Queue is unavailable."
            job.completed_at = datetime.now(UTC)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable."
            ) from exc
        job.status = ProcessingStatus.QUEUED.value
        job.provider_job_id = str(task.id)
    await session.commit()
    await session.refresh(job)
    return await _try_on_read(session, job)


@router.get("/try-ons/{job_id}", response_model=TryOnRead)
async def get_try_on(
    job_id: UUID,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> TryOnRead:
    result = await session.execute(select(TryOnJob).where(TryOnJob.id == job_id, TryOnJob.user_id == user_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on job not found.")
    return await _try_on_read(session, job)


@router.get("/try-ons/{job_id}/image")
async def get_try_on_image(
    job_id: UUID,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> Response:
    result = await session.execute(select(TryOnJob).where(TryOnJob.id == job_id, TryOnJob.user_id == user_id))
    job = result.scalar_one_or_none()
    if job is None or job.output_image_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on image not found.")
    image = await session.get(ImageAsset, job.output_image_id)
    if image is None or image.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on image not found.")
    content = await ObjectStorage(get_settings()).get_bytes(image.storage_key)
    return Response(content=content, media_type="image/png")

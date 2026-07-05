from datetime import UTC, datetime
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.enums import GarmentStatus
from aiwardrobe_core.image_validation import detect_image_content_type
from aiwardrobe_core.models import GarmentItem, ImageAsset
from aiwardrobe_core.schemas import GarmentItemRead, GarmentItemUpdate
from aiwardrobe_core.storage import ObjectStorage
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/items", tags=["garment-items"])


def item_read_model(item: GarmentItem) -> GarmentItemRead:
    return GarmentItemRead(
        id=item.id,
        title=item.title,
        category=item.category,
        season=list(item.season),
        main_color=item.main_color,
        confidence=item.confidence,
        status=item.status,
        availability_status=item.availability_status,
        designer_attributes=dict(item.designer_attributes),
    )


@router.get("", response_model=list[GarmentItemRead])
async def list_items(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> list[GarmentItemRead]:
    result = await session.execute(
        select(GarmentItem)
        .where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None))
        .order_by(GarmentItem.created_at.desc())
        .limit(100)
    )
    return [item_read_model(item) for item in result.scalars()]


@router.get("/{item_id}", response_model=GarmentItemRead)
async def get_item(item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> GarmentItemRead:
    return item_read_model(await load_item(session, user_id, item_id))


@router.get("/{item_id}/image")
async def get_item_image(item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> Response:
    item = await load_item(session, user_id, item_id)
    if item.original_image_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item has no stored image.")
    result = await session.execute(
        select(ImageAsset).where(ImageAsset.id == item.original_image_id, ImageAsset.user_id == user_id)
    )
    image = result.scalar_one_or_none()
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    try:
        content = await ObjectStorage(get_settings()).get_bytes(image.storage_key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Image storage is unavailable.") from exc
    media_type = detect_image_content_type(content) or "image/jpeg"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.patch("/{item_id}", response_model=GarmentItemRead)
async def update_item(
    item_id: UUID, payload: GarmentItemUpdate, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> GarmentItemRead:
    item = await load_item(session, user_id, item_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item_read_model(item)


@router.post("/{item_id}/confirm", response_model=GarmentItemRead)
async def confirm_item(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> GarmentItemRead:
    item = await load_item(session, user_id, item_id)
    item.status = GarmentStatus.CONFIRMED.value
    await session.commit()
    await session.refresh(item)
    return item_read_model(item)


@router.post("/{item_id}/hide", response_model=GarmentItemRead)
async def hide_item(item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> GarmentItemRead:
    item = await load_item(session, user_id, item_id)
    item.status = GarmentStatus.HIDDEN.value
    item.is_hidden = True
    await session.commit()
    await session.refresh(item)
    return item_read_model(item)


@router.post("/{item_id}/wear", response_model=GarmentItemRead)
async def wear_item(item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> GarmentItemRead:
    item = await load_item(session, user_id, item_id)
    item.wear_count += 1
    item.last_worn_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(item)
    return item_read_model(item)


@router.post("/{item_id}/research")
async def rerun_research(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_item(session, user_id, item_id)
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/generate-product-image")
async def generate_product_image(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_item(session, user_id, item_id)
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/find-product-photo")
async def find_product_photo(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_item(session, user_id, item_id)
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/find-similar")
async def find_similar(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_item(session, user_id, item_id)
    return {"id": item_id, "status": "queued"}


@router.post("/{item_id}/delete-original")
async def delete_original(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_item(session, user_id, item_id)
    return {"id": item_id, "status": "original_deleted"}


@router.delete("/{item_id}")
async def delete_item(
    item_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    item = await load_item(session, user_id, item_id)
    item.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"id": item_id, "status": "deleted"}


async def load_item(session: AsyncSession, user_id: UUID, item_id: UUID) -> GarmentItem:
    result = await session.execute(
        select(GarmentItem).where(
            GarmentItem.id == item_id,
            GarmentItem.user_id == user_id,
            GarmentItem.deleted_at.is_(None),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    return item

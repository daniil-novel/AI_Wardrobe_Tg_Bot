from uuid import UUID

from aiwardrobe_core.models import WishlistItem
from aiwardrobe_core.schemas import WishlistCreate, WishlistRead
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


def wishlist_read_model(item: WishlistItem) -> WishlistRead:
    return WishlistRead(
        id=item.id,
        title=item.title,
        source_url=item.source_url,
        status=item.status,
        notes=item.notes,
    )


@router.post("", response_model=WishlistRead)
async def create_wishlist_item(
    payload: WishlistCreate, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> WishlistRead:
    item = WishlistItem(
        user_id=user_id,
        title=payload.title,
        source_url=str(payload.source_url) if payload.source_url else None,
        notes=payload.notes,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return wishlist_read_model(item)


@router.get("", response_model=list[WishlistRead])
async def list_wishlist(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> list[WishlistRead]:
    result = await session.execute(
        select(WishlistItem).where(WishlistItem.user_id == user_id).order_by(WishlistItem.created_at.desc()).limit(100)
    )
    return [wishlist_read_model(item) for item in result.scalars()]


@router.patch("/{wishlist_id}", response_model=WishlistRead)
async def update_wishlist_item(
    wishlist_id: UUID, payload: WishlistCreate, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> WishlistRead:
    item = await load_wishlist_item(session, user_id, wishlist_id)
    item.title = payload.title
    item.source_url = str(payload.source_url) if payload.source_url else None
    item.notes = payload.notes
    await session.commit()
    await session.refresh(item)
    return wishlist_read_model(item)


@router.delete("/{wishlist_id}")
async def delete_wishlist_item(
    wishlist_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    item = await load_wishlist_item(session, user_id, wishlist_id)
    await session.delete(item)
    await session.commit()
    return {"id": wishlist_id, "status": "deleted"}


async def load_wishlist_item(session: AsyncSession, user_id: UUID, wishlist_id: UUID) -> WishlistItem:
    result = await session.execute(
        select(WishlistItem).where(WishlistItem.id == wishlist_id, WishlistItem.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist item not found.")
    return item

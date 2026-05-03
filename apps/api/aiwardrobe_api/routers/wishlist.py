from uuid import UUID, uuid4

from aiwardrobe_core.schemas import WishlistCreate, WishlistRead
from fastapi import APIRouter

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.post("", response_model=WishlistRead)
async def create_wishlist_item(payload: WishlistCreate) -> WishlistRead:
    return WishlistRead(
        id=uuid4(),
        title=payload.title,
        source_url=str(payload.source_url) if payload.source_url else None,
        status="idea",
        notes=payload.notes,
    )


@router.get("", response_model=list[WishlistRead])
async def list_wishlist() -> list[WishlistRead]:
    return []


@router.patch("/{wishlist_id}", response_model=WishlistRead)
async def update_wishlist_item(wishlist_id: UUID, payload: WishlistCreate) -> WishlistRead:
    return WishlistRead(
        id=wishlist_id,
        title=payload.title,
        source_url=str(payload.source_url) if payload.source_url else None,
        status="idea",
        notes=payload.notes,
    )


@router.delete("/{wishlist_id}")
async def delete_wishlist_item(wishlist_id: UUID) -> dict[str, UUID | str]:
    return {"id": wishlist_id, "status": "deleted"}

from uuid import UUID

from aiwardrobe_core.models import GarmentItem, MissingItemCard
from aiwardrobe_core.schemas import OutfitRequest
from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/designer", tags=["designer"])


@router.post("/wardrobe-gaps")
async def wardrobe_gaps(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> dict[str, object]:
    result = await session.execute(
        select(MissingItemCard)
        .where(MissingItemCard.user_id == user_id)
        .order_by(MissingItemCard.priority.desc(), MissingItemCard.created_at.desc())
        .limit(20)
    )
    cards = [
        {
            "id": str(card.id),
            "title": card.title,
            "reason": card.reason,
            "priority": card.priority,
            "category": card.category,
        }
        for card in result.scalars()
    ]
    return {"missing_items": cards}


@router.post("/missing-for-selected-items")
async def missing_for_selected(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, object]:
    if not payload.anchor_item_ids:
        return {"anchor_count": 0, "missing_items": []}
    owned_count = await session.scalar(
        select(func.count())
        .select_from(GarmentItem)
        .where(
            GarmentItem.user_id == user_id,
            GarmentItem.id.in_(payload.anchor_item_ids),
            GarmentItem.deleted_at.is_(None),
        )
    )
    return {"anchor_count": int(owned_count or 0), "missing_items": []}


@router.post("/rate-look")
async def rate_look(user_id: UUID = CurrentUser) -> dict[str, object]:
    _ = user_id
    return {
        "what_works": [],
        "what_to_improve": [],
        "safety_note": "Only clothing is evaluated; face, body and identity analysis are out of scope.",
    }

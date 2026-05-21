from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from aiwardrobe_core.models import (
    GarmentItem,
    LookCard,
    OutfitCard,
    PrivacyReceipt,
    PurchaseSimulation,
    Upload,
    User,
)
from aiwardrobe_core.schemas import PrivacyReceiptRead, PurchaseSimulationRead, PurchaseSimulationRequest
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(tags=["privacy-and-purchase"])


@router.post("/privacy/receipt/{upload_id}", response_model=PrivacyReceiptRead)
async def privacy_receipt(
    upload_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> PrivacyReceiptRead:
    result = await session.execute(
        select(PrivacyReceipt).where(PrivacyReceipt.upload_id == upload_id, PrivacyReceipt.user_id == user_id)
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Privacy receipt not found.")
    return PrivacyReceiptRead(
        upload_id=upload_id,
        ai_provider_used=receipt.ai_provider_used,
        model_used=receipt.model_used,
        original_saved=receipt.original_saved,
        research_used=receipt.research_used,
        training_allowed=receipt.training_allowed,
        deleted_original_at=receipt.deleted_original_at,
    )


@router.post("/purchase-simulator", response_model=PurchaseSimulationRead)
async def purchase_simulator(
    payload: PurchaseSimulationRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> PurchaseSimulationRead:
    item_count = await session.scalar(
        select(func.count())
        .select_from(GarmentItem)
        .where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None))
    )
    compatibility_count = min(int(item_count or 0), 5)
    duplicate_risk = Decimal("20") if compatibility_count < 3 else Decimal("60")
    buy_score = Decimal("70") if duplicate_risk < 50 else Decimal("45")
    simulation = PurchaseSimulation(
        user_id=user_id,
        product_description=payload.product_description,
        source_url=str(payload.source_url) if payload.source_url else None,
        buy_score=buy_score,
        duplicate_risk=duplicate_risk,
        compatibility_count=compatibility_count,
        scenario_coverage={"wardrobe_items_checked": compatibility_count},
        recommendation="Можно рассмотреть покупку." if buy_score >= 60 else "Лучше проверить дубли и сценарии носки.",
    )
    session.add(simulation)
    await session.commit()
    return PurchaseSimulationRead(
        buy_score=simulation.buy_score,
        duplicate_risk=simulation.duplicate_risk,
        compatibility_count=simulation.compatibility_count,
        scenario_coverage=simulation.scenario_coverage,
        recommendation=simulation.recommendation,
    )


@router.post("/capsules/build")
async def build_capsule(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> dict[str, object]:
    item_ids = await session.scalars(
        select(GarmentItem.id).where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None)).limit(12)
    )
    items = [str(item_id) for item_id in item_ids]
    return {"status": "queued" if items else "empty_wardrobe", "items": items, "outfit_count": 0}


@router.post("/challenges/no-buy")
async def no_buy_challenge(user_id: UUID = CurrentUser) -> dict[str, str]:
    _ = user_id
    return {"status": "started"}


@router.post("/share/outfit-card")
async def share_outfit_card(user_id: UUID = CurrentUser) -> dict[str, str]:
    _ = user_id
    return {"status": "queued"}


@router.post("/privacy/delete-me")
async def delete_my_data(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> dict[str, str | int]:
    now = datetime.now(UTC)
    deleted_uploads = await session.scalar(select(func.count()).select_from(Upload).where(Upload.user_id == user_id))
    await session.execute(update(GarmentItem).where(GarmentItem.user_id == user_id).values(deleted_at=now))
    await session.execute(update(LookCard).where(LookCard.user_id == user_id).values(deleted_at=now))
    await session.execute(delete(OutfitCard).where(OutfitCard.user_id == user_id))
    await session.execute(delete(Upload).where(Upload.user_id == user_id))
    await session.execute(update(User).where(User.id == user_id).values(deleted_at=now))
    await session.commit()
    return {"status": "deletion_completed", "deleted_uploads": int(deleted_uploads or 0)}

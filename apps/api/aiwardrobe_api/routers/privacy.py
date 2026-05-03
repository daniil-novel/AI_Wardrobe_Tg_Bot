from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.schemas import PrivacyReceiptRead, PurchaseSimulationRead, PurchaseSimulationRequest

router = APIRouter(tags=["privacy-and-purchase"])


@router.post("/privacy/receipt/{upload_id}", response_model=PrivacyReceiptRead)
async def privacy_receipt(upload_id: UUID) -> PrivacyReceiptRead:
    settings = get_settings()
    return PrivacyReceiptRead(
        upload_id=upload_id,
        ai_provider_used="openrouter",
        model_used=settings.openrouter_model_image,
        original_saved=True,
        research_used=False,
        training_allowed=False,
    )


@router.post("/purchase-simulator", response_model=PurchaseSimulationRead)
async def purchase_simulator(payload: PurchaseSimulationRequest) -> PurchaseSimulationRead:
    return PurchaseSimulationRead(
        buy_score=Decimal("42"),
        duplicate_risk=Decimal("70"),
        compatibility_count=2,
        scenario_coverage={"office": "low", "rain": "medium"},
        recommendation=(
            "Я бы не спешил покупать: похожая вещь уже есть, а новая закрывает мало сценариев."
        ),
    )


@router.post("/capsules/build")
async def build_capsule() -> dict[str, object]:
    return {"status": "queued", "items": [], "outfit_count": 0}


@router.post("/challenges/no-buy")
async def no_buy_challenge() -> dict[str, str]:
    return {"status": "started"}


@router.post("/share/outfit-card")
async def share_outfit_card() -> dict[str, str]:
    return {"status": "queued"}

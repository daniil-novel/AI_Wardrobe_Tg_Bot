from decimal import Decimal
from uuid import UUID, uuid4

from aiwardrobe_core.schemas import StyleDnaRead, StyleRuleCreate, StyleRuleRead, WardrobeHealthRead
from fastapi import APIRouter

router = APIRouter(tags=["style"])


@router.get("/style-dna", response_model=StyleDnaRead)
async def get_style_dna() -> StyleDnaRead:
    return StyleDnaRead(
        dominant_styles=["casual", "minimal"],
        preferred_color_families=["neutral", "blue"],
        preferred_silhouettes=["relaxed"],
        confidence=Decimal("0.40"),
    )


@router.patch("/style-dna", response_model=StyleDnaRead)
async def patch_style_dna(payload: StyleDnaRead) -> StyleDnaRead:
    return payload


@router.post("/style-dna/calibrate")
async def calibrate_style_dna() -> dict[str, str]:
    return {"status": "queued"}


@router.get("/wardrobe/health", response_model=WardrobeHealthRead)
async def wardrobe_health() -> WardrobeHealthRead:
    return WardrobeHealthRead(score=Decimal("62"), missing_roles=["rain shoes"], orphan_items=[])


@router.post("/rules", response_model=StyleRuleRead)
async def create_rule(payload: StyleRuleCreate) -> StyleRuleRead:
    return StyleRuleRead(
        id=uuid4(),
        natural_language_rule=payload.natural_language_rule,
        parsed_rule={},
        enabled=True,
    )


@router.get("/rules", response_model=list[StyleRuleRead])
async def list_rules() -> list[StyleRuleRead]:
    return []


@router.patch("/rules/{rule_id}", response_model=StyleRuleRead)
async def patch_rule(rule_id: UUID, payload: StyleRuleCreate) -> StyleRuleRead:
    return StyleRuleRead(
        id=rule_id,
        natural_language_rule=payload.natural_language_rule,
        parsed_rule={},
        enabled=True,
    )

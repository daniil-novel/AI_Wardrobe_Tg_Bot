from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter

from aiwardrobe_core.schemas import OutfitRead, OutfitRequest

router = APIRouter(prefix="/outfits", tags=["outfits"])


def sample_outfit(outfit_id: UUID | None = None, prompt: str | None = None) -> OutfitRead:
    return OutfitRead(
        id=outfit_id or uuid4(),
        title=prompt or "Город + метро + офис",
        score=Decimal("92"),
        comfort_score=Decimal("86"),
        explanation="Нейтральная база, фактура денима и удобная обувь.",
        designer_reasoning={
            "color": "нейтральная база + холодный деним",
            "practicality": "верхний слой можно снять в метро",
        },
    )


@router.post("/recommend", response_model=list[OutfitRead])
async def recommend(payload: OutfitRequest) -> list[OutfitRead]:
    return [sample_outfit(prompt=payload.prompt)]


@router.post("/from-prompt", response_model=list[OutfitRead])
async def from_prompt(payload: OutfitRequest) -> list[OutfitRead]:
    return [sample_outfit(prompt=payload.prompt)]


@router.post("/recommend-with-anchors", response_model=list[OutfitRead])
async def recommend_with_anchors(payload: OutfitRequest) -> list[OutfitRead]:
    return [sample_outfit(prompt=f"Образ с {len(payload.anchor_item_ids)} выбранными вещами")]


@router.get("", response_model=list[OutfitRead])
async def list_outfits() -> list[OutfitRead]:
    return [sample_outfit()]


@router.get("/{outfit_id}", response_model=OutfitRead)
async def get_outfit(outfit_id: UUID) -> OutfitRead:
    return sample_outfit(outfit_id)


@router.post("/{outfit_id}/favorite", response_model=OutfitRead)
async def favorite_outfit(outfit_id: UUID) -> OutfitRead:
    return sample_outfit(outfit_id).model_copy(update={"is_favorite": True})


@router.post("/{outfit_id}/rate")
async def rate_outfit(outfit_id: UUID) -> dict[str, UUID | str]:
    return {"id": outfit_id, "status": "rated"}


@router.post("/{outfit_id}/wear")
async def wear_outfit(outfit_id: UUID) -> dict[str, UUID | str]:
    return {"id": outfit_id, "status": "worn"}


@router.post("/{outfit_id}/select")
async def select_outfit(outfit_id: UUID) -> dict[str, UUID | str]:
    return {"id": outfit_id, "status": "selected"}


@router.post("/stress-test")
async def stress_test(payload: OutfitRequest) -> dict[str, object]:
    return {
        "score": 82,
        "what_works": ["нейтральная база", "удобный слой"],
        "risks": ["проверьте обувь при длительной ходьбе"],
        "request": payload.model_dump(mode="json"),
    }


@router.post("/explain-exclusion")
async def explain_exclusion(payload: OutfitRequest) -> dict[str, str]:
    return {"reason": "Вещь может не подходить по погоде, формальности или пользовательским правилам."}


@router.delete("/{outfit_id}")
async def delete_outfit(outfit_id: UUID) -> dict[str, UUID | str]:
    return {"id": outfit_id, "status": "deleted"}

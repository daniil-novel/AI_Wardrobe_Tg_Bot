from uuid import uuid4

from fastapi import APIRouter

from aiwardrobe_core.schemas import OutfitRequest

router = APIRouter(prefix="/designer", tags=["designer"])


@router.post("/wardrobe-gaps")
async def wardrobe_gaps() -> dict[str, object]:
    return {
        "missing_items": [
            {
                "id": str(uuid4()),
                "title": "Лаконичные тёмные ботинки",
                "reason": "Закроют дождливую погоду и smart casual сценарии.",
                "priority": 90,
            }
        ]
    }


@router.post("/missing-for-selected-items")
async def missing_for_selected(payload: OutfitRequest) -> dict[str, object]:
    return {"anchor_count": len(payload.anchor_item_ids), "missing_items": []}


@router.post("/rate-look")
async def rate_look() -> dict[str, object]:
    return {
        "what_works": ["нейтральная база", "спокойный casual-настрой"],
        "what_to_improve": ["добавить верхний слой для структуры"],
        "safety_note": "Оценивается только одежда, не лицо или тело.",
    }

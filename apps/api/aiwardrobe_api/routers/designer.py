from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.llm_gateway import LlmGateway, LlmGatewayError
from aiwardrobe_core.models import GarmentItem, MissingItemCard
from aiwardrobe_core.schemas import DesignerChatRequest, DesignerChatResponse, OutfitRequest
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/designer", tags=["designer"])


def _wardrobe_item_payload(item: GarmentItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "title": item.title,
        "category": item.category,
        "season": item.season,
        "color": item.main_color,
        "brand": item.designer_attributes.get("brand"),
        "model_name": item.designer_attributes.get("model_name"),
        "availability_status": item.availability_status,
    }


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


@router.post("/chat", response_model=DesignerChatResponse)
async def designer_chat(
    payload: DesignerChatRequest,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> DesignerChatResponse:
    result = await session.execute(
        select(GarmentItem)
        .where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None))
        .order_by(GarmentItem.updated_at.desc())
        .limit(40)
    )
    items = list(result.scalars())
    wardrobe = [_wardrobe_item_payload(item) for item in items]
    prompt = (
        "Ты — персональный стилист в Telegram Mini App. Отвечай на русском, конкретно и практично. "
        "Учитывай только одежду, погоду, сценарий дня и предпочтения пользователя; не оценивай лицо, тело, "
        "возраст, привлекательность или личность. Если гардероб пуст или данных мало, "
        "честно скажи, что нужно добавить. "
        "Верни JSON: reply:string, outfit_id:null, outfit_title:null, item_count:number. "
        f"Гардероб={wardrobe}. "
        f"Погода={payload.weather_context or 'не указана'}. "
        f"Сценарий={payload.scenario or 'не указан'}. "
        f"Предпочтения={payload.preferences or 'не указаны'}. "
        f"Сообщение пользователя={payload.message}"
    )
    try:
        generated = await LlmGateway(get_settings()).generate_text_json(prompt, "DesignerChatResponse")
    except LlmGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI designer is unavailable: configure OPENROUTER_API_KEY.",
        ) from exc
    return DesignerChatResponse(
        reply=str(generated.get("reply") or "Расскажите подробнее, куда идёте и насколько тепло хотите одеться."),
        outfit_id=None,
        outfit_title=None,
        item_count=len(items),
    )

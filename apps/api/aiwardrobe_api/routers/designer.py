from decimal import Decimal
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.llm_gateway import LlmGateway, LlmGatewayError
from aiwardrobe_core.models import GarmentItem, MissingItemCard, OutfitCard, OutfitItem
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
    if not cards:
        # No curated missing-item cards yet: derive gaps from the live wardrobe
        # so the tool stays consistent with the wardrobe health widget.
        from aiwardrobe_api.routers.style import calculate_wardrobe_health

        health = await calculate_wardrobe_health(session, user_id)
        cards = [
            {"id": f"health-{index}", "title": role, "reason": None, "priority": "high", "category": None}
            for index, role in enumerate(health.missing_roles)
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
        "возраст, привлекательность или личность. Если пользователь мерзнет — предлагай теплее, чем требует "
        "погода; если ему быстро жарко — легче. Если гардероб пуст или данных мало, честно скажи, что добавить. "
        "Верни ТОЛЬКО JSON: reply:string (твой ответ пользователю, 1-4 предложения), "
        "outfit:null ЛИБО объект {title:string (короткое название образа на русском), "
        "explanation:string (почему образ работает), score:number 0-100, comfort_score:number 0-100, "
        "item_ids:array of strings — ТОЛЬКО id вещей из списка гардероба ниже}. "
        "Если пользователь просит образ/что надеть — обязательно предложи outfit из его вещей. Не выдумывай id. "
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

    reply = str(generated.get("reply") or "Расскажите подробнее, куда идёте и насколько тепло хотите одеться.")
    outfit_data = generated.get("outfit")
    outfit_id: UUID | None = None
    outfit_title: str | None = None
    outfit_explanation: str | None = None
    outfit_score: float | None = None
    outfit_item_ids: list[UUID] = []
    if isinstance(outfit_data, dict) and items:
        raw_ids = outfit_data.get("item_ids", [])
        selected_ids = set()
        for raw_id in raw_ids if isinstance(raw_ids, list) else []:
            try:
                selected_ids.add(UUID(str(raw_id)))
            except ValueError:
                continue
        selected_items = [item for item in items if item.id in selected_ids]
        if selected_items:
            outfit = OutfitCard(
                user_id=user_id,
                title=str(outfit_data.get("title") or "Образ дня"),
                generation_context={
                    "source": "designer_chat",
                    "scenario": payload.scenario,
                    "weather": payload.weather_context,
                    "preferences": payload.preferences,
                },
                designer_reasoning={"source": "designer_chat", "selected_item_count": len(selected_items)},
                explanation=str(outfit_data.get("explanation") or ""),
                score=Decimal(str(outfit_data.get("score") or "75")),
                comfort_score=Decimal(str(outfit_data.get("comfort_score") or outfit_data.get("score") or "75")),
            )
            session.add(outfit)
            await session.flush()
            for item in selected_items:
                session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, role=item.category))
            await session.commit()
            outfit_id = outfit.id
            outfit_title = outfit.title
            outfit_explanation = outfit.explanation
            outfit_score = float(outfit.score)
            outfit_item_ids = [item.id for item in selected_items]

    return DesignerChatResponse(
        reply=reply,
        outfit_id=outfit_id,
        outfit_title=outfit_title,
        outfit_explanation=outfit_explanation,
        outfit_score=outfit_score,
        outfit_item_ids=outfit_item_ids,
        item_count=len(items),
    )

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from aiwardrobe_core.models import GarmentItem, OutfitCard, OutfitGenerationRequest, OutfitItem, OutfitMemory
from aiwardrobe_core.schemas import OutfitRead, OutfitRequest
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/outfits", tags=["outfits"])


def outfit_read_model(outfit: OutfitCard) -> OutfitRead:
    return OutfitRead(
        id=outfit.id,
        title=outfit.title,
        score=outfit.score,
        comfort_score=outfit.comfort_score,
        explanation=outfit.explanation,
        designer_reasoning=dict(outfit.designer_reasoning),
        is_favorite=outfit.is_favorite,
        item_ids=[link.item_id for link in outfit.items],
    )


@router.post("/recommend", response_model=list[OutfitRead])
async def recommend(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> list[OutfitRead]:
    return await create_outfit_recommendations(session, user_id, payload)


@router.post("/from-prompt", response_model=list[OutfitRead])
async def from_prompt(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> list[OutfitRead]:
    return await create_outfit_recommendations(session, user_id, payload)


@router.post("/recommend-with-anchors", response_model=list[OutfitRead])
async def recommend_with_anchors(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> list[OutfitRead]:
    return await create_outfit_recommendations(session, user_id, payload)


@router.get("", response_model=list[OutfitRead])
async def list_outfits(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> list[OutfitRead]:
    result = await session.execute(
        select(OutfitCard)
        .options(selectinload(OutfitCard.items))
        .where(OutfitCard.user_id == user_id)
        .order_by(OutfitCard.created_at.desc())
        .limit(100)
    )
    return [outfit_read_model(outfit) for outfit in result.scalars()]


@router.get("/{outfit_id}", response_model=OutfitRead)
async def get_outfit(outfit_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> OutfitRead:
    return outfit_read_model(await load_outfit(session, user_id, outfit_id))


@router.post("/{outfit_id}/favorite", response_model=OutfitRead)
async def favorite_outfit(
    outfit_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> OutfitRead:
    outfit = await load_outfit(session, user_id, outfit_id)
    outfit.is_favorite = True
    await session.commit()
    await session.refresh(outfit)
    return outfit_read_model(outfit)


@router.post("/{outfit_id}/rate")
async def rate_outfit(
    outfit_id: UUID, rating: str = "ok", user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    outfit = await load_outfit(session, user_id, outfit_id)
    outfit.user_rating = rating
    session.add(OutfitMemory(user_id=user_id, outfit_id=outfit_id, action_type="rated", feedback=rating))
    await session.commit()
    return {"id": outfit_id, "status": "rated"}


@router.post("/{outfit_id}/wear")
async def wear_outfit(
    outfit_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_outfit(session, user_id, outfit_id)
    session.add(OutfitMemory(user_id=user_id, outfit_id=outfit_id, action_type="worn", context={}))
    await session.commit()
    return {"id": outfit_id, "status": "worn"}


@router.post("/{outfit_id}/select")
async def select_outfit(
    outfit_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    outfit = await load_outfit(session, user_id, outfit_id)
    outfit.selected_at = datetime.now(UTC)
    session.add(OutfitMemory(user_id=user_id, outfit_id=outfit_id, action_type="selected", context={}))
    await session.commit()
    return {"id": outfit_id, "status": "selected"}


@router.post("/stress-test")
async def stress_test(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, object]:
    result = await session.execute(
        select(GarmentItem.id).where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None))
    )
    item_count = len(result.scalars().all())
    return {
        "score": min(100, 40 + item_count * 5),
        "what_works": ["используются вещи из вашего гардероба"] if item_count else [],
        "risks": ["гардероб пуст, добавьте вещи"] if item_count == 0 else [],
        "request": payload.model_dump(mode="json"),
    }


@router.post("/explain-exclusion")
async def explain_exclusion(
    payload: OutfitRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, str]:
    if payload.anchor_item_ids:
        result = await session.execute(
            select(GarmentItem.id).where(GarmentItem.user_id == user_id, GarmentItem.id.in_(payload.anchor_item_ids))
        )
        found = set(result.scalars().all())
        missing = [str(item_id) for item_id in payload.anchor_item_ids if item_id not in found]
        if missing:
            return {"reason": "Одна или несколько вещей не найдены в вашем гардеробе."}
    return {"reason": "Вещь может быть исключена по погоде, формальности, доступности или пользовательским правилам."}


@router.delete("/{outfit_id}")
async def delete_outfit(
    outfit_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    outfit = await load_outfit(session, user_id, outfit_id)
    await session.delete(outfit)
    await session.commit()
    return {"id": outfit_id, "status": "deleted"}


async def create_outfit_recommendations(
    session: AsyncSession, user_id: UUID, payload: OutfitRequest
) -> list[OutfitRead]:
    item_query = select(GarmentItem).where(GarmentItem.user_id == user_id, GarmentItem.deleted_at.is_(None))
    if payload.anchor_item_ids:
        item_query = item_query.where(GarmentItem.id.in_(payload.anchor_item_ids))
    result = await session.execute(item_query.limit(max(payload.variants_count, 1)))
    items = list(result.scalars())

    generation = OutfitGenerationRequest(
        user_id=user_id,
        anchor_item_ids=[str(item_id) for item_id in payload.anchor_item_ids],
        manual_weather=payload.weather,
        event_type=payload.event_type,
        variants_count=payload.variants_count,
        prompt=payload.prompt,
        status="completed",
    )
    session.add(generation)

    if not items:
        await session.commit()
        return []

    event_note = f" под сценарий «{payload.event_type}»" if payload.event_type else ""
    outfit = OutfitCard(
        user_id=user_id,
        title="Образ из вашего гардероба",
        generation_context={"request_id": str(generation.id), "source": "wardrobe_rules", "prompt": payload.prompt},
        weather_snapshot=payload.weather,
        designer_reasoning={"source": "гардероб", "item_count": len(items)},
        explanation=f"Собрано из {len(items)} вещей вашего гардероба{event_note}.",
        score=Decimal("75"),
        comfort_score=Decimal("75"),
    )
    session.add(outfit)
    await session.flush()
    for item in items:
        session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, role=item.category or None))
    await session.commit()
    return [await load_outfit_read(session, user_id, outfit.id)]


async def load_outfit_read(session: AsyncSession, user_id: UUID, outfit_id: UUID) -> OutfitRead:
    result = await session.execute(
        select(OutfitCard)
        .options(selectinload(OutfitCard.items))
        .where(OutfitCard.id == outfit_id, OutfitCard.user_id == user_id)
    )
    outfit = result.scalar_one_or_none()
    if outfit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found.")
    return outfit_read_model(outfit)


async def load_outfit(session: AsyncSession, user_id: UUID, outfit_id: UUID) -> OutfitCard:
    result = await session.execute(
        select(OutfitCard)
        .options(selectinload(OutfitCard.items))
        .where(OutfitCard.id == outfit_id, OutfitCard.user_id == user_id)
    )
    outfit = result.scalar_one_or_none()
    if outfit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found.")
    return outfit

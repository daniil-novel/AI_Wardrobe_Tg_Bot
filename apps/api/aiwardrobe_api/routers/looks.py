from datetime import UTC, datetime
from uuid import UUID

from aiwardrobe_core.models import LookCard
from aiwardrobe_core.schemas import LookCardRead
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/looks", tags=["looks"])


def look_read_model(look: LookCard) -> LookCardRead:
    return LookCardRead(
        id=look.id,
        title=look.title,
        is_favorite=look.is_favorite,
        style_tags=list(look.style_tags),
        designer_reasoning=dict(look.designer_reasoning),
        confidence=look.confidence,
    )


@router.get("", response_model=list[LookCardRead])
async def list_looks(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> list[LookCardRead]:
    result = await session.execute(
        select(LookCard)
        .where(LookCard.user_id == user_id, LookCard.deleted_at.is_(None))
        .order_by(LookCard.created_at.desc())
        .limit(100)
    )
    return [look_read_model(look) for look in result.scalars()]


@router.get("/{look_id}", response_model=LookCardRead)
async def get_look(look_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> LookCardRead:
    return look_read_model(await load_look(session, user_id, look_id))


@router.post("/{look_id}/favorite", response_model=LookCardRead)
async def favorite_look(look_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> LookCardRead:
    look = await load_look(session, user_id, look_id)
    look.is_favorite = True
    await session.commit()
    await session.refresh(look)
    return look_read_model(look)


@router.delete("/{look_id}/favorite", response_model=LookCardRead)
async def unfavorite_look(
    look_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> LookCardRead:
    look = await load_look(session, user_id, look_id)
    look.is_favorite = False
    await session.commit()
    await session.refresh(look)
    return look_read_model(look)


@router.post("/{look_id}/generate-similar")
async def generate_similar(
    look_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    await load_look(session, user_id, look_id)
    return {"id": look_id, "status": "queued"}


@router.delete("/{look_id}")
async def delete_look(
    look_id: UUID, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> dict[str, UUID | str]:
    look = await load_look(session, user_id, look_id)
    look.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"id": look_id, "status": "deleted"}


async def load_look(session: AsyncSession, user_id: UUID, look_id: UUID) -> LookCard:
    result = await session.execute(
        select(LookCard).where(
            LookCard.id == look_id,
            LookCard.user_id == user_id,
            LookCard.deleted_at.is_(None),
        )
    )
    look = result.scalar_one_or_none()
    if look is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found.")
    return look

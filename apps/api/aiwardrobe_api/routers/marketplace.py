from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.models import MarketplaceResult
from aiwardrobe_core.schemas import MarketplaceResultRead, MarketplaceSearchRequest
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/search-similar", response_model=list[MarketplaceResultRead])
async def search_similar(
    payload: MarketplaceSearchRequest, user_id: UUID = CurrentUser, session: AsyncSession = DbSession
) -> list[MarketplaceResultRead]:
    settings = get_settings()
    if not settings.enable_marketplace_search:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Marketplace search is disabled until a production provider adapter is configured.",
        )
    result = await session.execute(
        select(MarketplaceResult)
        .where(MarketplaceResult.user_id == user_id, MarketplaceResult.title.ilike(f"%{payload.query}%"))
        .order_by(MarketplaceResult.created_at.desc())
        .limit(20)
    )
    return [
        MarketplaceResultRead(
            id=item.id,
            marketplace=item.marketplace,
            title=item.title,
            url=item.url,
            price=item.price,
            match_confidence=item.match_confidence,
        )
        for item in result.scalars()
    ]

from decimal import Decimal
from uuid import uuid4

from aiwardrobe_core.schemas import MarketplaceResultRead, MarketplaceSearchRequest
from fastapi import APIRouter

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/search-similar", response_model=list[MarketplaceResultRead])
async def search_similar(payload: MarketplaceSearchRequest) -> list[MarketplaceResultRead]:
    return [
        MarketplaceResultRead(
            id=uuid4(),
            marketplace=payload.marketplaces[0],
            title=f"Похожий товар: {payload.query}",
            url="https://example.com/product",
            price=Decimal("0"),
            match_confidence=Decimal("0.70"),
        )
    ]

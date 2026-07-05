from decimal import Decimal
from uuid import uuid4

import pytest
from aiwardrobe_api.routers.style import calculate_wardrobe_health
from aiwardrobe_core.models import GarmentItem


class FakeScalarResult:
    def __init__(self, items: list[GarmentItem]) -> None:
        self.items = items

    def __iter__(self):
        return iter(self.items)


class FakeResult:
    def __init__(self, items: list[GarmentItem]) -> None:
        self.items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.items)


class FakeSession:
    def __init__(self, items: list[GarmentItem]) -> None:
        self.items = items

    async def execute(self, query):
        _ = query
        return FakeResult(self.items)


def garment(title: str, category: str, seasons: list[str], confidence: str = "0.90") -> GarmentItem:
    return GarmentItem(
        user_id=uuid4(),
        title=title,
        category=category,
        main_color="чёрный",
        season=seasons,
        confidence=Decimal(confidence),
        availability_status="available",
        is_hidden=False,
    )


@pytest.mark.asyncio
async def test_calculate_wardrobe_health_empty_wardrobe() -> None:
    health = await calculate_wardrobe_health(FakeSession([]), uuid4())  # type: ignore[arg-type]

    assert health.score == 0
    assert "Добавьте верх" in health.missing_roles[0]


@pytest.mark.asyncio
async def test_calculate_wardrobe_health_uses_real_items() -> None:
    health = await calculate_wardrobe_health(
        FakeSession(
            [
                garment("Футболка", "top", ["summer"]),
                garment("Брюки", "bottom", ["all_season"]),
                garment("Кроссовки", "shoes", ["all_season"]),
                garment("Пальто", "outerwear", ["winter"], "0.50"),
            ]
        ),
        uuid4(),
    )  # type: ignore[arg-type]

    assert health.score > 80
    assert health.coverage_by_event["item_count"] == 4
    assert health.orphan_items == ["Пальто: низкая уверенность распознавания"]

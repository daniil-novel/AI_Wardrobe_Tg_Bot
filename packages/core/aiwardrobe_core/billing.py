from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from aiwardrobe_core.config import Settings, get_settings
from aiwardrobe_core.enums import PaymentProviderCode, SubscriptionPlan


@dataclass(frozen=True)
class Plan:
    code: SubscriptionPlan
    title: str
    monthly_price: Decimal
    currency: str
    item_limit: int | None
    ai_analysis_limit: int | None
    avatar_generation_limit: int
    try_on_limit: int
    features: tuple[str, ...]
    pricing_status: str = "proposed"


@dataclass(frozen=True)
class PaymentEvent:
    provider: PaymentProviderCode
    provider_payment_id: str
    status: str
    amount: Decimal
    currency: str
    raw_event: dict[str, object]


class PaymentProvider(Protocol):
    code: PaymentProviderCode

    async def create_invoice(self, user_id: str, plan: Plan) -> str:
        """Return provider-specific invoice URL or Telegram invoice payload id."""

    async def parse_event(self, payload: dict[str, object]) -> PaymentEvent:
        """Normalize provider webhook or Telegram payment event."""


def get_plans(settings: Settings | None = None) -> dict[SubscriptionPlan, Plan]:
    resolved = settings or get_settings()
    return {
        SubscriptionPlan.FREE: Plan(
            code=SubscriptionPlan.FREE,
            title="Free",
            monthly_price=Decimal(0),
            currency="RUB",
            item_limit=resolved.free_items_limit,
            ai_analysis_limit=resolved.free_ai_analyses_per_month,
            avatar_generation_limit=0,
            try_on_limit=0,
            features=("selection_editor", "basic_outfits", "basic_weather", "limited_research"),
        ),
        SubscriptionPlan.PREMIUM: Plan(
            code=SubscriptionPlan.PREMIUM,
            title="Premium",
            monthly_price=Decimal(resolved.premium_monthly_price_rub),
            currency="RUB",
            item_limit=resolved.premium_items_limit,
            ai_analysis_limit=resolved.premium_ai_analyses_per_month,
            avatar_generation_limit=resolved.premium_avatar_generations_per_month,
            try_on_limit=resolved.premium_try_ons_per_month,
            features=(
                "avatar_try_on",
                "full_research",
                "look_analysis",
                "unlimited_favorites",
                "wardrobe_analytics",
                "priority_queue",
            ),
        ),
        SubscriptionPlan.PRO: Plan(
            code=SubscriptionPlan.PRO,
            title="Pro",
            monthly_price=Decimal(resolved.pro_monthly_price_rub),
            currency="RUB",
            item_limit=None,
            ai_analysis_limit=None,
            avatar_generation_limit=resolved.pro_avatar_generations_per_month,
            try_on_limit=resolved.pro_try_ons_per_month,
            features=(
                "avatar_try_on",
                "multi_wardrobe",
                "export",
                "capsules",
                "trip_packing",
                "stylist_mode",
            ),
        ),
    }

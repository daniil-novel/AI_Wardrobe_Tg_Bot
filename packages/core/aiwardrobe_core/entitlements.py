import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_core.billing import get_plans
from aiwardrobe_core.config import Settings, get_settings
from aiwardrobe_core.enums import SubscriptionPlan
from aiwardrobe_core.models import PromoCode, PromoRedemption, Subscription, User


class PromoCodeError(ValueError):
    """Domain error safe to return without exposing promo storage details."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EffectiveAccess:
    plan: SubscriptionPlan
    source: str
    expires_at: datetime | None
    features: tuple[str, ...]


def normalize_promo_code(code: str) -> str:
    return "".join(character for character in code.strip().upper() if character.isalnum() or character == "-")


def hash_promo_code(code: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    secret = (resolved.promo_hash_secret or resolved.jwt_secret_key).encode()
    return hmac.new(secret, normalize_promo_code(code).encode(), sha256).hexdigest()


def generate_promo_code() -> str:
    return f"AW-1DAY-{secrets.token_urlsafe(12).upper()}"


def _plan_rank(plan: SubscriptionPlan) -> int:
    return {
        SubscriptionPlan.FREE: 0,
        SubscriptionPlan.PREMIUM: 1,
        SubscriptionPlan.PRO: 2,
    }[plan]


async def resolve_effective_access(
    session: AsyncSession,
    user_id: UUID,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> EffectiveAccess:
    resolved_now = now or datetime.now(UTC)
    resolved_settings = settings or get_settings()
    user = await session.get(User, user_id)
    legacy_plan = SubscriptionPlan(user.subscription_plan) if user else SubscriptionPlan.FREE
    access = EffectiveAccess(
        plan=legacy_plan,
        source="user_profile" if legacy_plan != SubscriptionPlan.FREE else "free",
        expires_at=None,
        features=get_plans(resolved_settings)[legacy_plan].features,
    )

    subscription_result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.current_period_end.desc().nullslast())
    )
    subscription = subscription_result.scalars().first()
    if subscription and (
        subscription.current_period_end is None or subscription.current_period_end >= resolved_now.date()
    ):
        subscription_plan = SubscriptionPlan(subscription.plan)
        if _plan_rank(subscription_plan) >= _plan_rank(access.plan):
            access = EffectiveAccess(
                plan=subscription_plan,
                source="subscription",
                expires_at=(
                    datetime.combine(subscription.current_period_end, datetime.max.time(), tzinfo=UTC)
                    if subscription.current_period_end
                    else None
                ),
                features=get_plans(resolved_settings)[subscription_plan].features,
            )

    promo_result = await session.execute(
        select(PromoRedemption)
        .where(
            PromoRedemption.user_id == user_id,
            PromoRedemption.revoked_at.is_(None),
            PromoRedemption.expires_at > resolved_now,
        )
        .order_by(PromoRedemption.expires_at.desc())
    )
    promo = promo_result.scalars().first()
    if promo:
        promo_plan = SubscriptionPlan(promo.plan)
        if _plan_rank(promo_plan) >= _plan_rank(access.plan):
            access = EffectiveAccess(
                plan=promo_plan,
                source="promo",
                expires_at=promo.expires_at,
                features=get_plans(resolved_settings)[promo_plan].features,
            )
    return access


async def redeem_promo_code(
    session: AsyncSession,
    user_id: UUID,
    code: str,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> PromoRedemption:
    resolved_now = now or datetime.now(UTC)
    code_hash = hash_promo_code(code, settings)
    promo_result = await session.execute(select(PromoCode).where(PromoCode.code_hash == code_hash).with_for_update())
    promo = promo_result.scalar_one_or_none()
    if promo is None:
        raise PromoCodeError("invalid", "Промокод не найден.")
    if not promo.enabled:
        raise PromoCodeError("disabled", "Промокод отключён.")
    if promo.valid_from > resolved_now or (promo.valid_until and promo.valid_until <= resolved_now):
        raise PromoCodeError("expired", "Срок действия промокода закончился.")

    existing_result = await session.execute(
        select(PromoRedemption).where(
            PromoRedemption.promo_code_id == promo.id,
            PromoRedemption.user_id == user_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if existing.revoked_at is None and existing.expires_at > resolved_now:
            return existing
        raise PromoCodeError("already_redeemed", "Этот промокод уже был использован.")
    if promo.redemption_count >= promo.max_redemptions:
        raise PromoCodeError("limit_reached", "Лимит активаций промокода исчерпан.")

    redemption = PromoRedemption(
        promo_code_id=promo.id,
        user_id=user_id,
        plan=promo.plan,
        redeemed_at=resolved_now,
        expires_at=resolved_now + timedelta(hours=promo.duration_hours),
    )
    promo.redemption_count += 1
    session.add(redemption)
    await session.flush()
    return redemption

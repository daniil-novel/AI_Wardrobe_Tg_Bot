from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiwardrobe_core.config import Settings
from aiwardrobe_core.entitlements import PromoCodeError, hash_promo_code, redeem_promo_code
from aiwardrobe_core.enums import SubscriptionPlan
from aiwardrobe_core.models import PromoCode, PromoRedemption


def result_with(value: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_promo_hash_is_normalized_and_keyed() -> None:
    first = Settings(jwt_secret_key="a" * 48)
    second = Settings(jwt_secret_key="b" * 48)

    assert hash_promo_code(" aw-1day-demo ", first) == hash_promo_code("AW-1DAY-DEMO", first)
    assert hash_promo_code("AW-1DAY-DEMO", first) != hash_promo_code("AW-1DAY-DEMO", second)


@pytest.mark.asyncio
async def test_redeem_promo_grants_exact_duration_and_increments_limit() -> None:
    now = datetime(2026, 7, 28, 12, tzinfo=UTC)
    promo = PromoCode(
        id=uuid4(),
        code_hash=hash_promo_code("AW-1DAY-TEST", Settings(jwt_secret_key="s" * 48)),
        label="One day test",
        plan=SubscriptionPlan.PREMIUM.value,
        duration_hours=24,
        max_redemptions=1,
        redemption_count=0,
        valid_from=now - timedelta(minutes=1),
        enabled=True,
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_with(promo), result_with(None)])
    session.flush = AsyncMock()
    user_id = uuid4()

    redemption = await redeem_promo_code(
        session,
        user_id,
        "AW-1DAY-TEST",
        now=now,
        settings=Settings(jwt_secret_key="s" * 48),
    )

    assert redemption.user_id == user_id
    assert redemption.plan == SubscriptionPlan.PREMIUM.value
    assert redemption.expires_at == now + timedelta(hours=24)
    assert promo.redemption_count == 1
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_redeem_promo_is_idempotent_while_existing_grant_is_active() -> None:
    now = datetime(2026, 7, 28, 12, tzinfo=UTC)
    promo = PromoCode(
        id=uuid4(),
        code_hash="hash",
        label="One day test",
        plan=SubscriptionPlan.PREMIUM.value,
        duration_hours=24,
        max_redemptions=1,
        redemption_count=1,
        valid_from=now - timedelta(minutes=1),
        enabled=True,
    )
    existing = PromoRedemption(
        id=uuid4(),
        promo_code_id=promo.id,
        user_id=uuid4(),
        plan=SubscriptionPlan.PREMIUM.value,
        redeemed_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=23),
    )
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[result_with(promo), result_with(existing)])
    session.flush = AsyncMock()

    redemption = await redeem_promo_code(session, existing.user_id, "any", now=now)

    assert redemption is existing
    assert promo.redemption_count == 1
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_redeem_expired_promo_is_rejected() -> None:
    now = datetime(2026, 7, 28, 12, tzinfo=UTC)
    promo = PromoCode(
        id=uuid4(),
        code_hash="hash",
        label="Expired",
        plan=SubscriptionPlan.PREMIUM.value,
        duration_hours=24,
        max_redemptions=1,
        redemption_count=0,
        valid_from=now - timedelta(days=2),
        valid_until=now,
        enabled=True,
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_with(promo))

    with pytest.raises(PromoCodeError, match="закончился"):
        await redeem_promo_code(session, uuid4(), "any", now=now)

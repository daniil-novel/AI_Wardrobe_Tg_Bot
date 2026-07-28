from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiwardrobe_core.billing import get_plans
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import SubscriptionPlan
from aiwardrobe_core.models import User
from aiwardrobe_core.usage import UsageQuotaExceeded, month_start, request_limit, reserve_billable_request


def empty_scalar_result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    return result


def test_month_start_uses_calendar_month_in_utc() -> None:
    assert month_start(datetime(2026, 8, 1, 1, tzinfo=UTC)) == datetime(2026, 8, 1, tzinfo=UTC)


def test_commercial_plan_has_explicit_generation_limits() -> None:
    plans = get_plans(Settings())

    assert request_limit(plans[SubscriptionPlan.PREMIUM], "generate_avatar") == 2
    assert request_limit(plans[SubscriptionPlan.PREMIUM], "virtual_try_on") == 6
    assert request_limit(plans[SubscriptionPlan.PRO], "virtual_try_on") == 15


@pytest.mark.asyncio
async def test_reservation_rejects_exhausted_monthly_quota() -> None:
    user_id = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[user_id, 2])
    session.get = AsyncMock(
        return_value=User(
            id=user_id,
            telegram_id=123,
            subscription_plan=SubscriptionPlan.FREE.value,
        )
    )
    session.execute = AsyncMock(side_effect=[empty_scalar_result(), empty_scalar_result()])
    session.flush = AsyncMock()

    with pytest.raises(UsageQuotaExceeded) as exc_info:
        await reserve_billable_request(
            session,
            user_id,
            uuid4(),
            "analyze_image",
            "provider/model",
            settings=Settings(free_ai_analyses_per_month=2),
            idempotent=False,
        )

    assert exc_info.value.limit == 2
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_open_build_still_audits_without_enforcing_paywall_quota() -> None:
    user_id = uuid4()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=user_id)
    session.get = AsyncMock(
        return_value=User(
            id=user_id,
            telegram_id=124,
            subscription_plan=SubscriptionPlan.FREE.value,
        )
    )
    session.execute = AsyncMock(side_effect=[empty_scalar_result(), empty_scalar_result()])
    session.flush = AsyncMock()

    request = await reserve_billable_request(
        session,
        user_id,
        uuid4(),
        "analyze_image",
        "provider/model",
        settings=Settings(subscriptions_enabled=False, free_ai_analyses_per_month=0),
        idempotent=False,
    )

    assert request.status == "queued"
    session.add.assert_called_once_with(request)
    session.flush.assert_awaited_once()

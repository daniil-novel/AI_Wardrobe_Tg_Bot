from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_core.billing import Plan, get_plans
from aiwardrobe_core.config import Settings, get_settings
from aiwardrobe_core.entitlements import EffectiveAccess, resolve_effective_access
from aiwardrobe_core.enums import ProcessingStatus
from aiwardrobe_core.models import AiRequest, User

BILLABLE_REQUEST_TYPES = frozenset({"analyze_image", "generate_avatar", "virtual_try_on"})


class UsageQuotaExceeded(ValueError):
    def __init__(self, request_type: str, limit: int) -> None:
        self.request_type = request_type
        self.limit = limit
        super().__init__(f"Monthly {request_type} quota of {limit} is exhausted.")


def month_start(now: datetime) -> datetime:
    resolved = now.astimezone(UTC)
    return datetime(resolved.year, resolved.month, 1, tzinfo=UTC)


def request_limit(plan: Plan, request_type: str) -> int | None:
    if request_type == "analyze_image":
        return plan.ai_analysis_limit
    if request_type == "generate_avatar":
        return plan.avatar_generation_limit
    if request_type == "virtual_try_on":
        return plan.try_on_limit
    raise ValueError(f"Unsupported billable request type: {request_type}")


async def reserve_billable_request(
    session: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    request_type: str,
    model: str,
    *,
    provider: str = "openrouter",
    now: datetime | None = None,
    settings: Settings | None = None,
    idempotent: bool = True,
) -> AiRequest:
    if request_type not in BILLABLE_REQUEST_TYPES:
        raise ValueError(f"Unsupported billable request type: {request_type}")

    resolved_settings = settings or get_settings()
    resolved_now = now or datetime.now(UTC)

    # The user row is the quota lock: parallel uploads for the same account cannot
    # both observe the same remaining slot and oversubscribe it.
    locked_user = await session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    if locked_user is None:
        raise ValueError("User not found.")

    if idempotent:
        existing_result = await session.execute(
            select(AiRequest)
            .where(AiRequest.task_id == task_id, AiRequest.request_type == request_type)
            .order_by(AiRequest.created_at.desc())
        )
        existing = existing_result.scalars().first()
        if existing is not None:
            existing.status = ProcessingStatus.QUEUED.value
            existing.error_code = None
            existing.provider = provider
            existing.model = model
            return existing

    access: EffectiveAccess = await resolve_effective_access(
        session,
        user_id,
        now=resolved_now,
        settings=resolved_settings,
    )
    plan = get_plans(resolved_settings)[access.plan]
    limit = None if not resolved_settings.subscriptions_enabled else request_limit(plan, request_type)
    if limit is not None:
        used = await session.scalar(
            select(func.count(AiRequest.id)).where(
                AiRequest.user_id == user_id,
                AiRequest.request_type == request_type,
                AiRequest.status != ProcessingStatus.FAILED.value,
                AiRequest.created_at >= month_start(resolved_now),
            )
        )
        if int(used or 0) >= limit:
            raise UsageQuotaExceeded(request_type, limit)

    request = AiRequest(
        user_id=user_id,
        task_id=task_id,
        provider=provider,
        model=model,
        request_type=request_type,
        status=ProcessingStatus.QUEUED.value,
        cost_usd=Decimal("0"),
    )
    session.add(request)
    await session.flush()
    return request


async def finalize_billable_request(
    session: AsyncSession,
    user_id: UUID,
    task_id: UUID,
    request_type: str,
    model: str,
    final_status: str,
    *,
    provider: str = "openrouter",
    latency_ms: int = 0,
    error_code: str | None = None,
) -> AiRequest:
    result = await session.execute(
        select(AiRequest)
        .where(
            AiRequest.user_id == user_id,
            AiRequest.task_id == task_id,
            AiRequest.request_type == request_type,
        )
        .order_by(AiRequest.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    request = result.scalar_one_or_none()
    if request is None:
        request = AiRequest(
            user_id=user_id,
            task_id=task_id,
            provider=provider,
            model=model,
            request_type=request_type,
            status=final_status,
            cost_usd=Decimal("0"),
        )
        session.add(request)
    request.status = final_status
    request.provider = provider
    request.model = model
    request.error_code = error_code
    request.latency_ms = max(0, latency_ms)
    await session.flush()
    return request

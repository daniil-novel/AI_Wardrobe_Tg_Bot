from uuid import UUID

from aiwardrobe_core.billing import get_plans
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.entitlements import PromoCodeError, redeem_promo_code, resolve_effective_access
from aiwardrobe_core.enums import SubscriptionPlan
from aiwardrobe_core.schemas import BillingAccessRead, PlanRead, PromoRedeemRead, PromoRedeemRequest
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiwardrobe_api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanRead])
async def plans() -> list[PlanRead]:
    return [
        PlanRead(
            code=plan.code.value,
            title=plan.title,
            monthly_price=plan.monthly_price,
            currency=plan.currency,
            item_limit=plan.item_limit,
            ai_analysis_limit=plan.ai_analysis_limit,
            avatar_generation_limit=plan.avatar_generation_limit,
            try_on_limit=plan.try_on_limit,
            features=list(plan.features),
            pricing_status=plan.pricing_status,
        )
        for plan in get_plans().values()
    ]


@router.get("/me", response_model=BillingAccessRead)
async def billing_access(user_id: UUID = CurrentUser, session: AsyncSession = DbSession) -> BillingAccessRead:
    settings = get_settings()
    access = await resolve_effective_access(session, user_id, settings=settings)
    return BillingAccessRead(
        enabled=settings.subscriptions_enabled,
        payments_enabled=settings.enable_billing_payments,
        plan=access.plan.value,
        source=access.source,
        expires_at=access.expires_at,
        features=list(access.features),
    )


@router.post("/promos/redeem", response_model=PromoRedeemRead)
async def redeem_promo(
    payload: PromoRedeemRequest,
    user_id: UUID = CurrentUser,
    session: AsyncSession = DbSession,
) -> PromoRedeemRead:
    settings = get_settings()
    try:
        redemption = await redeem_promo_code(session, user_id, payload.code, settings=settings)
    except PromoCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    plan = get_plans(settings)[SubscriptionPlan(redemption.plan)]
    return PromoRedeemRead(
        plan=redemption.plan,
        expires_at=redemption.expires_at,
        features=list(plan.features),
    )

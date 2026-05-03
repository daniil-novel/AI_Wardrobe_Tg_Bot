from aiwardrobe_core.billing import get_plans
from aiwardrobe_core.schemas import PlanRead
from fastapi import APIRouter

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanRead])
async def plans() -> list[PlanRead]:
    return [
        PlanRead(
            code=plan.code.value,
            item_limit=plan.item_limit,
            ai_analysis_limit=plan.ai_analysis_limit,
            features=list(plan.features),
        )
        for plan in get_plans().values()
    ]

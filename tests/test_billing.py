from aiwardrobe_core.billing import get_plans
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import SubscriptionPlan


def test_plan_limits_follow_settings() -> None:
    settings = Settings(
        free_items_limit=20,
        free_ai_analyses_per_month=5,
        premium_items_limit=500,
        premium_ai_analyses_per_month=100,
    )
    plans = get_plans(settings)
    assert plans[SubscriptionPlan.FREE].item_limit == 20
    assert plans[SubscriptionPlan.FREE].ai_analysis_limit == 5
    assert plans[SubscriptionPlan.PREMIUM].item_limit == 500
    assert plans[SubscriptionPlan.PRO].item_limit is None

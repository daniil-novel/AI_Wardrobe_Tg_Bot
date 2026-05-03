import asyncio
from typing import Any

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.llm_gateway import LlmGateway
from celery.utils.log import get_task_logger

from .celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def analyze_upload(self: Any, upload_id: str, signed_image_url: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required; mock AI mode is disabled.")

    async def run() -> dict[str, Any]:
        result = await LlmGateway(settings).analyze_image(
            signed_image_url,
            "Analyze the clothing image and return image_type, item fields, season, color, "
            "style, designer_attributes and confidence.",
        )
        return result.model_dump()

    logger.info("Analyzing upload %s", upload_id)
    return asyncio.run(run())


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def research_item(self: Any, item_id: str, text_description: str) -> dict[str, Any]:
    if not text_description:
        raise ValueError("Research requires text description; private photos must not be sent to web search.")
    logger.info("Research queued for item %s", item_id)
    return {"item_id": item_id, "status": "pending_provider_integration"}


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_outfit(self: Any, user_id: str, context: dict[str, Any]) -> dict[str, Any]:
    logger.info("Generating outfit for user %s", user_id)
    return {"user_id": user_id, "context": context, "status": "pending_provider_integration"}


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_notification(self: Any, telegram_id: int, text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for notifications.")
    logger.info("Notification queued for Telegram user %s", telegram_id)
    return {"telegram_id": telegram_id, "status": "pending_bot_delivery", "text": text}

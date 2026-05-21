import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.enums import GarmentStatus, ProcessingStatus
from aiwardrobe_core.llm_gateway import LlmGateway
from aiwardrobe_core.models import AiRequest, GarmentItem, PrivacyReceipt, Upload
from celery.utils.log import get_task_logger
from sqlalchemy import select

from .celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def analyze_upload(self: Any, upload_id: str, signed_image_url: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required; mock AI mode is disabled.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(Upload).where(Upload.id == UUID(upload_id)))
            upload = result.scalar_one_or_none()
            if upload is None:
                raise ValueError("Upload not found.")
            upload.status = ProcessingStatus.PROCESSING.value
            await session.commit()

            try:
                analysis = await LlmGateway(settings).analyze_image(
                    signed_image_url,
                    "Analyze the clothing image and return image_type, item fields, season, color, "
                    "style, designer_attributes and confidence.",
                )
                item = GarmentItem(
                    user_id=upload.user_id,
                    title=analysis.title,
                    category=analysis.category,
                    description=analysis.description,
                    main_color=analysis.main_color,
                    season=analysis.season,
                    style_archetype=analysis.style_archetype,
                    designer_attributes={
                        **analysis.designer_attributes,
                        "designer_reasoning": analysis.designer_reasoning,
                    },
                    confidence=Decimal(str(analysis.confidence)),
                    status=GarmentStatus.NEEDS_CONFIRMATION.value,
                    source_upload_id=upload.id,
                    original_image_id=upload.original_image_id,
                )
                receipt = PrivacyReceipt(
                    user_id=upload.user_id,
                    upload_id=upload.id,
                    model_used=settings.openrouter_model_image,
                    original_saved=True,
                    research_used=False,
                    training_allowed=False,
                )
                upload.status = ProcessingStatus.COMPLETED.value
                upload.completed_at = datetime.now(UTC)
                upload.confidence = Decimal(str(analysis.confidence))
                session.add_all(
                    [
                        item,
                        receipt,
                        AiRequest(
                            user_id=upload.user_id,
                            task_id=upload.id,
                            model=settings.openrouter_model_image,
                            request_type="analyze_image",
                            status=ProcessingStatus.COMPLETED.value,
                            cost_usd=Decimal("0"),
                        ),
                    ]
                )
                await session.commit()
                return analysis.model_dump()
            except Exception as exc:
                upload.status = ProcessingStatus.FAILED.value
                upload.error_code = exc.__class__.__name__
                upload.error_message = str(exc)[:1000]
                session.add(
                    AiRequest(
                        user_id=upload.user_id,
                        task_id=upload.id,
                        model=settings.openrouter_model_image,
                        request_type="analyze_image",
                        status=ProcessingStatus.FAILED.value,
                        error_code=exc.__class__.__name__,
                        cost_usd=Decimal("0"),
                    )
                )
                await session.commit()
                raise

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

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.enums import GarmentStatus, ProcessingStatus
from aiwardrobe_core.llm_gateway import LlmGateway
from aiwardrobe_core.logging import hash_identifier
from aiwardrobe_core.models import AiRequest, GarmentItem, OutfitCard, OutfitItem, PrivacyReceipt, Upload
from celery.exceptions import Ignore
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
    started = time.perf_counter()
    try:
        result = asyncio.run(run())
    except Exception:
        logger.exception("AI upload analysis failed", extra={"upload_id_hash": hash_identifier(upload_id)})
        raise
    logger.info(
        "AI upload analysis completed",
        extra={
            "upload_id_hash": hash_identifier(upload_id),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return result


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def research_item(self: Any, item_id: str, text_description: str) -> dict[str, Any]:
    if not text_description:
        raise ValueError("Research requires text description; private photos must not be sent to web search.")

    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for item research.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(GarmentItem).where(GarmentItem.id == UUID(item_id)))
            item = result.scalar_one_or_none()
            if item is None:
                raise Ignore()

            research = await LlmGateway(settings).generate_text_json(
                (
                    "Research this clothing item using only the supplied text. Return JSON with "
                    "summary:string and sources:array of source labels or urls. Do not infer private "
                    f"attributes. Item: {text_description}"
                ),
                "ItemResearch",
            )
            summary = str(research.get("summary", "")).strip()
            sources_raw = research.get("sources", [])
            sources = sources_raw if isinstance(sources_raw, list) else []
            item.research_summary = summary
            item.research_sources = sources
            session.add(
                AiRequest(
                    user_id=item.user_id,
                    task_id=item.id,
                    model=settings.openrouter_model_text,
                    request_type="research_item",
                    status=ProcessingStatus.COMPLETED.value,
                    cost_usd=Decimal("0"),
                )
            )
            await session.commit()
            return {"item_id": item_id, "status": ProcessingStatus.COMPLETED.value, "summary": summary}

    logger.info("Research queued for item %s", item_id)
    started = time.perf_counter()
    result = asyncio.run(run())
    logger.info(
        "Item research completed",
        extra={"item_id_hash": hash_identifier(item_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
    )
    return result


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_outfit(self: Any, user_id: str, context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required for outfit generation.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GarmentItem)
                .where(GarmentItem.user_id == UUID(user_id), GarmentItem.deleted_at.is_(None))
                .order_by(GarmentItem.updated_at.desc())
                .limit(30)
            )
            items = list(result.scalars())
            if not items:
                return {"user_id": user_id, "status": "empty_wardrobe", "outfit_id": None}

            wardrobe_payload = [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "category": item.category,
                    "season": item.season,
                    "color": item.main_color,
                    "status": item.status,
                }
                for item in items
            ]
            generated = await LlmGateway(settings).generate_text_json(
                (
                    "Generate one practical outfit from this wardrobe and context. Return JSON with "
                    "title:string, explanation:string, score:number, item_ids:array of selected ids. "
                    f"Wardrobe={wardrobe_payload}; Context={context}"
                ),
                "OutfitGeneration",
            )
            selected_ids = {
                UUID(str(item_id)) for item_id in generated.get("item_ids", []) if isinstance(item_id, str) and item_id
            }
            selected_items = [item for item in items if item.id in selected_ids] or items[: min(4, len(items))]
            outfit = OutfitCard(
                user_id=UUID(user_id),
                title=str(generated.get("title") or "Outfit"),
                generation_context=context,
                designer_reasoning={"provider": "openrouter", "selected_item_count": len(selected_items)},
                explanation=str(generated.get("explanation") or ""),
                score=Decimal(str(generated.get("score") or "75")),
                comfort_score=Decimal(str(generated.get("comfort_score") or generated.get("score") or "75")),
            )
            session.add(outfit)
            await session.flush()
            for item in selected_items:
                session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, role=item.category))
            session.add(
                AiRequest(
                    user_id=UUID(user_id),
                    task_id=outfit.id,
                    model=settings.openrouter_model_text,
                    request_type="generate_outfit",
                    status=ProcessingStatus.COMPLETED.value,
                    cost_usd=Decimal("0"),
                )
            )
            await session.commit()
            return {"user_id": user_id, "status": ProcessingStatus.COMPLETED.value, "outfit_id": str(outfit.id)}

    logger.info("Generating outfit for user %s", user_id)
    started = time.perf_counter()
    result = asyncio.run(run())
    logger.info(
        "Outfit generation completed",
        extra={"user_id_hash": hash_identifier(user_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
    )
    return result


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_notification(self: Any, telegram_id: int, text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for notifications.")
    logger.info("Notification queued for Telegram user %s", telegram_id)
    return {"telegram_id": telegram_id, "status": "pending_bot_delivery", "text": text}

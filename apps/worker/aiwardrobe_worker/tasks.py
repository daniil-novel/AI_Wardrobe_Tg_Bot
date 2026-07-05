import asyncio
import time
from base64 import b64encode
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.enums import GarmentStatus, ProcessingStatus, ProvenanceLabel
from aiwardrobe_core.image_validation import (
    ImageValidationError,
    detect_image_content_type,
    validate_image_content,
)
from aiwardrobe_core.llm_gateway import LlmGateway
from aiwardrobe_core.logging import hash_identifier
from aiwardrobe_core.models import AiRequest, GarmentItem, ImageAsset, OutfitCard, OutfitItem, PrivacyReceipt, Upload
from aiwardrobe_core.storage import ObjectStorage, build_storage_key
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from sqlalchemy import select

from .celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def analyze_upload(self: Any, upload_id: str, storage_key: str) -> dict[str, Any]:
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
                if storage_key.startswith(("http://", "https://")):
                    image_url = storage_key
                else:
                    # The AI provider cannot reach the private object network, so the
                    # image travels inline as a data URL instead of a presigned link.
                    content = await ObjectStorage(settings).get_bytes(storage_key)
                    content_type = detect_image_content_type(content) or "image/jpeg"
                    image_url = f"data:{content_type};base64,{b64encode(content).decode()}"
                analysis = await LlmGateway(settings).analyze_image(
                    image_url,
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
def transfer_telegram_upload(self: Any, upload_id: str) -> dict[str, Any]:
    """Download a Telegram photo through the Bot API and move it into private object storage."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for Telegram file transfer.")

    async def fail_upload(upload: Upload, code: str, message: str, session: Any) -> None:
        upload.status = ProcessingStatus.FAILED.value
        upload.error_code = code
        upload.error_message = message[:1000]
        await session.commit()

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(Upload).where(Upload.id == UUID(upload_id)))
            upload = result.scalar_one_or_none()
            if upload is None:
                raise ValueError("Upload not found.")
            if upload.original_image_id is not None or upload.status == ProcessingStatus.COMPLETED.value:
                return {"upload_id": upload_id, "status": upload.status, "skipped": "already_transferred"}
            if not upload.telegram_file_id:
                await fail_upload(upload, "missing_telegram_file", "Upload has no Telegram file id.", session)
                raise Ignore()

            api_base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    file_info = await client.get(f"{api_base}/getFile", params={"file_id": upload.telegram_file_id})
                    file_info.raise_for_status()
                    file_path = file_info.json().get("result", {}).get("file_path")
                    if not file_path:
                        await fail_upload(
                            upload, "telegram_file_unavailable", "Telegram did not return file path.", session
                        )
                        raise Ignore()
                    file_response = await client.get(
                        f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
                    )
                    file_response.raise_for_status()
                    content = file_response.content
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    # Client errors (bad or expired file id) never recover; do not burn retries.
                    await fail_upload(
                        upload,
                        "telegram_file_unavailable",
                        f"Telegram file API returned {exc.response.status_code}.",
                        session,
                    )
                    raise Ignore() from exc
                raise

            try:
                content_type = validate_image_content(
                    content, settings.max_upload_bytes, settings.allowed_upload_content_type_set
                )
            except ImageValidationError as exc:
                await fail_upload(upload, exc.code, exc.message, session)
                raise Ignore() from exc

            storage_key = build_storage_key(upload.user_id, "originals", file_path.split("/")[-1])
            await ObjectStorage(settings).put_bytes(storage_key, content, content_type)

            image = ImageAsset(
                user_id=upload.user_id,
                source_type="telegram",
                storage_key=storage_key,
                provenance_label=ProvenanceLabel.USER_PROCESSED.value,
            )
            session.add(image)
            await session.flush()
            upload.original_image_id = image.id
            upload.status = ProcessingStatus.UPLOADED.value
            upload.error_code = None
            upload.error_message = None
            task = analyze_upload.delay(upload_id, storage_key)
            upload.task_id = str(task.id)
            upload.status = ProcessingStatus.QUEUED.value
            await session.commit()
            return {"upload_id": upload_id, "status": upload.status, "storage_key_set": True}

    logger.info("Transferring Telegram upload %s", upload_id)
    started = time.perf_counter()
    result = asyncio.run(run())
    logger.info(
        "Telegram upload transfer finished",
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

    async def run() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": telegram_id, "text": text},
            )
            response.raise_for_status()
        return {"telegram_id": telegram_id, "status": "delivered"}

    logger.info("Sending notification to Telegram user hash %s", hash_identifier(str(telegram_id)))
    return asyncio.run(run())

import asyncio
import time
from base64 import b64encode
from collections.abc import Coroutine
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.enums import GarmentStatus, ProcessingStatus, ProvenanceLabel
from aiwardrobe_core.image_processing import ImageProcessingError, create_white_background_product_image
from aiwardrobe_core.image_validation import (
    ImageValidationError,
    detect_image_content_type,
    validate_image_content,
)
from aiwardrobe_core.llm_gateway import LlmGateway, LlmGatewayError
from aiwardrobe_core.logging import hash_identifier
from aiwardrobe_core.models import (
    AiRequest,
    AvatarMeasurement,
    AvatarProfile,
    GarmentItem,
    ImageAsset,
    LookCard,
    LookItem,
    OutfitCard,
    OutfitItem,
    PrivacyReceipt,
    TryOnItem,
    TryOnJob,
    Upload,
    User,
)
from aiwardrobe_core.storage import ObjectStorage, build_storage_key
from aiwardrobe_core.usage import UsageQuotaExceeded, finalize_billable_request, reserve_billable_request
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from sqlalchemy import select, update

from .celery_app import celery_app

logger = get_task_logger(__name__)

_worker_event_loop: asyncio.AbstractEventLoop | None = None


def run_worker_coroutine[CoroutineResult](
    coroutine: Coroutine[Any, Any, CoroutineResult],
) -> CoroutineResult:
    """Run async Celery work on one event loop per prefork process."""
    global _worker_event_loop
    if _worker_event_loop is None or _worker_event_loop.is_closed():
        _worker_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_event_loop)
    return _worker_event_loop.run_until_complete(coroutine)


def find_possible_duplicate(
    title: str, category: str, main_color: str | None, existing_items: list[GarmentItem]
) -> GarmentItem | None:
    """Best-effort match so a re-uploaded garment is flagged as a possible duplicate, not silently copied."""
    normalized_title = title.casefold().strip()
    for item in existing_items:
        existing_title = (item.title or "").casefold().strip()
        if existing_title == normalized_title:
            return item
        if (
            item.category == category
            and (item.main_color or "").casefold() == (main_color or "").casefold()
            and (normalized_title in existing_title or existing_title in normalized_title)
        ):
            return item
    return None


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def analyze_upload(self: Any, upload_id: str, storage_key: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ai_analysis_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required in API mode; mock AI mode is disabled.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(Upload).where(Upload.id == UUID(upload_id)))
            upload = result.scalar_one_or_none()
            if upload is None:
                raise ValueError("Upload not found.")
            if upload.status == ProcessingStatus.COMPLETED.value:
                # Retries after a post-commit hiccup must not duplicate the cards.
                return {"image_type": "unknown", "items_created": 0, "skipped": "already_completed"}
            user_id = upload.user_id
            upload.status = ProcessingStatus.PROCESSING.value
            await session.commit()

            try:
                gateway = LlmGateway(settings)
                content: bytes | None = None
                if storage_key.startswith(("http://", "https://")):
                    image_url = storage_key
                else:
                    # The AI provider cannot reach the private object network, so the
                    # image travels inline as a data URL instead of a presigned link.
                    content = await ObjectStorage(settings).get_bytes(storage_key)
                    content_type = detect_image_content_type(content) or "image/jpeg"
                    image_url = f"data:{content_type};base64,{b64encode(content).decode()}"

                analysis = await gateway.analyze_image_items(image_url)
                garments = analysis.items[:6]

                existing_result = await session.execute(
                    select(GarmentItem).where(
                        GarmentItem.user_id == upload.user_id,
                        GarmentItem.deleted_at.is_(None),
                    )
                )
                existing_items = list(existing_result.scalars())

                created_items: list[GarmentItem] = []
                failed_titles: list[str] = []
                degraded_titles: list[str] = []
                for garment in garments:
                    try:
                        async with session.begin_nested():
                            processed_image_id = None
                            try:
                                product_hint = f"{garment.title} ({garment.main_color}, {garment.category})"
                                product_bytes = await gateway.generate_product_image(
                                    image_url, product_hint, settings.product_image_background
                                )
                                processed_key = build_storage_key(
                                    upload.user_id, "processed", f"{upload.id}-{len(created_items)}.png"
                                )
                                await ObjectStorage(settings).put_bytes(processed_key, product_bytes, "image/png")
                                processed_image = ImageAsset(
                                    user_id=upload.user_id,
                                    source_type="processed",
                                    storage_key=processed_key,
                                    provenance_label=ProvenanceLabel.USER_PROCESSED.value,
                                    generated_prompt=(
                                        f"Product photo: {product_hint} on "
                                        f"{settings.product_image_background} background."
                                    ),
                                )
                                session.add(processed_image)
                                await session.flush()
                                processed_image_id = processed_image.id
                            except Exception:
                                # Product extraction is best-effort: fall back to the normalized original.
                                degraded_titles.append(garment.title)
                                if content is not None:
                                    try:
                                        processed_content = create_white_background_product_image(content)
                                        processed_key = build_storage_key(
                                            upload.user_id, "processed", f"{upload.id}-{len(created_items)}.jpg"
                                        )
                                        await ObjectStorage(settings).put_bytes(
                                            processed_key, processed_content, "image/jpeg"
                                        )
                                        processed_image = ImageAsset(
                                            user_id=upload.user_id,
                                            source_type="processed",
                                            storage_key=processed_key,
                                            provenance_label=ProvenanceLabel.USER_PROCESSED.value,
                                            generated_prompt="Normalized item photo on a white product background.",
                                        )
                                        session.add(processed_image)
                                        await session.flush()
                                        processed_image_id = processed_image.id
                                    except ImageProcessingError:
                                        logger.warning(
                                            "Product image normalization failed",
                                            extra={"upload_id_hash": hash_identifier(upload_id)},
                                        )

                            duplicate_of = find_possible_duplicate(
                                garment.title, garment.category, garment.main_color, existing_items
                            )
                            attributes = {
                                **garment.designer_attributes.model_dump(mode="json"),
                                "brand": garment.brand,
                                "model_name": garment.model_name,
                                "visual_identifiers": garment.visual_identifiers,
                                "designer_reasoning": garment.designer_reasoning,
                            }
                            if duplicate_of is not None:
                                attributes["possible_duplicate_of"] = str(duplicate_of.id)
                                attributes["possible_duplicate_title"] = duplicate_of.title
                            item = GarmentItem(
                                user_id=upload.user_id,
                                title=garment.title[:255],
                                category=garment.category[:128],
                                description=garment.description,
                                main_color=garment.main_color,
                                season=garment.season,
                                style_archetype=garment.style_archetype,
                                designer_attributes=attributes,
                                confidence=Decimal(str(garment.confidence)),
                                status=GarmentStatus.NEEDS_CONFIRMATION.value,
                                source_upload_id=upload.id,
                                original_image_id=upload.original_image_id,
                                processed_image_id=processed_image_id,
                            )
                            session.add(item)
                            await session.flush()
                            created_items.append(item)
                    except Exception:
                        # One broken garment must not lose the rest of the photo.
                        failed_titles.append(garment.title)
                        logger.warning(
                            "Garment card creation failed",
                            extra={"upload_id_hash": hash_identifier(upload_id)},
                        )
                if not created_items:
                    raise LlmGatewayError("No garment card could be created from the photo.")
                await session.flush()

                # TZ 6.2: a look photo becomes a favorite LookCard linked to draft item cards.
                if created_items and (analysis.image_type in {"look", "look_photo"} or len(created_items) > 1):
                    look = LookCard(
                        user_id=upload.user_id,
                        title=analysis.look_title or "Загруженный образ",
                        source_type="upload",
                        source_upload_id=upload.id,
                        original_image_id=upload.original_image_id,
                        is_favorite=True,
                        style_tags=analysis.look_style_tags,
                        designer_reasoning={"why_it_works": analysis.look_summary},
                        confidence=Decimal(str(max((g.confidence for g in garments), default=0))),
                    )
                    session.add(look)
                    await session.flush()
                    for sort_order, item in enumerate(created_items):
                        session.add(LookItem(look_id=look.id, item_id=item.id, sort_order=sort_order))

                receipt = PrivacyReceipt(
                    user_id=upload.user_id,
                    upload_id=upload.id,
                    ai_provider_used=gateway.last_provider or settings.ai_analysis_provider,
                    model_used=gateway.last_model or settings.ai_analysis_model,
                    original_saved=True,
                    research_used=False,
                    training_allowed=False,
                )
                upload.status = ProcessingStatus.COMPLETED.value
                upload.completed_at = datetime.now(UTC)
                upload.confidence = Decimal(str(max((g.confidence for g in garments), default=0)))
                session.add(receipt)
                await finalize_billable_request(
                    session,
                    upload.user_id,
                    upload.id,
                    "analyze_image",
                    gateway.last_model or settings.ai_analysis_model,
                    ProcessingStatus.COMPLETED.value,
                    provider=gateway.last_provider or settings.ai_analysis_provider,
                )

                # TZ: tell the user which garments could not become full product cards.
                notes: list[str] = []
                if len(analysis.items) > len(garments):
                    notes.append(f"На фото нашлось {len(analysis.items)} вещей — добавлены первые {len(garments)}.")
                if failed_titles:
                    notes.append("Не получилось добавить: " + ", ".join(failed_titles) + ".")
                if degraded_titles:
                    notes.append(
                        "Не получилось сделать товарное фото для: "
                        + ", ".join(degraded_titles)
                        + " — в карточке останется исходный кадр."
                    )
                telegram_id: int | None = None
                if notes:
                    telegram_result = await session.execute(select(User.telegram_id).where(User.id == upload.user_id))
                    telegram_id = telegram_result.scalar_one_or_none()
                await session.commit()

                if notes and telegram_id is not None:
                    try:
                        # After the commit nothing may raise, or a retry would duplicate the cards.
                        send_notification.delay(telegram_id, " ".join(notes))
                    except Exception:
                        logger.warning(
                            "Failed to enqueue garment notification",
                            extra={"upload_id_hash": hash_identifier(upload_id)},
                        )
                return {
                    "image_type": analysis.image_type,
                    "items_created": len(created_items),
                    "items_failed": len(failed_titles),
                    "titles": [item.title for item in created_items],
                }
            except Exception as exc:
                # Drop every half-created card first: the retry will rebuild them from scratch.
                await session.rollback()
                await session.execute(
                    update(Upload)
                    .where(Upload.id == UUID(upload_id))
                    .values(
                        status=ProcessingStatus.FAILED.value,
                        error_code=exc.__class__.__name__,
                        error_message=str(exc)[:1000],
                    )
                )
                await finalize_billable_request(
                    session,
                    user_id,
                    UUID(upload_id),
                    "analyze_image",
                    gateway.last_model or settings.ai_analysis_model,
                    ProcessingStatus.FAILED.value,
                    provider=gateway.last_provider or settings.ai_analysis_provider,
                    error_code=exc.__class__.__name__,
                )
                await session.commit()
                raise

    logger.info("Analyzing upload %s", upload_id)
    started = time.perf_counter()
    try:
        result = run_worker_coroutine(run())
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

            try:
                await reserve_billable_request(
                    session,
                    upload.user_id,
                    upload.id,
                    "analyze_image",
                    settings.ai_analysis_model,
                    provider=settings.ai_analysis_provider,
                    settings=settings,
                )
            except UsageQuotaExceeded as exc:
                await fail_upload(upload, "quota_exceeded", str(exc), session)
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
    result = run_worker_coroutine(run())
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
    if not settings.ai_analysis_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required for item research in API mode.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(GarmentItem).where(GarmentItem.id == UUID(item_id)))
            item = result.scalar_one_or_none()
            if item is None:
                raise Ignore()

            gateway = LlmGateway(settings)
            research = await gateway.generate_text_json(
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
                    provider=gateway.last_provider or settings.ai_analysis_provider,
                    model=gateway.last_model or settings.ai_analysis_model,
                    request_type="research_item",
                    status=ProcessingStatus.COMPLETED.value,
                    cost_usd=Decimal("0"),
                )
            )
            await session.commit()
            return {"item_id": item_id, "status": ProcessingStatus.COMPLETED.value, "summary": summary}

    logger.info("Research queued for item %s", item_id)
    started = time.perf_counter()
    result = run_worker_coroutine(run())
    logger.info(
        "Item research completed",
        extra={"item_id_hash": hash_identifier(item_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
    )
    return result


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_outfit(self: Any, user_id: str, context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ai_analysis_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required for outfit generation in API mode.")

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
            gateway = LlmGateway(settings)
            generated = await gateway.generate_text_json(
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
                designer_reasoning={
                    "provider": gateway.last_provider or settings.ai_analysis_provider,
                    "selected_item_count": len(selected_items),
                },
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
                    provider=gateway.last_provider or settings.ai_analysis_provider,
                    model=gateway.last_model or settings.ai_analysis_model,
                    request_type="generate_outfit",
                    status=ProcessingStatus.COMPLETED.value,
                    cost_usd=Decimal("0"),
                )
            )
            await session.commit()
            return {"user_id": user_id, "status": ProcessingStatus.COMPLETED.value, "outfit_id": str(outfit.id)}

    logger.info("Generating outfit for user %s", user_id)
    started = time.perf_counter()
    result = run_worker_coroutine(run())
    logger.info(
        "Outfit generation completed",
        extra={"user_id_hash": hash_identifier(user_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
    )
    return result


DESIGNER_CHAT_SCHEMA_PROMPT = (
    "Ты — персональный AI-стилист в приложении цифрового гардероба. Отвечай тепло и по делу, на русском. "
    "Учитывай гардероб пользователя, погоду и его личные предпочтения (например, если человек мерзнет — "
    "предлагай теплее, чем требует погода). Верни ТОЛЬКО JSON-объект с полями: "
    "reply (string, твой ответ пользователю на русском, 1-4 предложения), "
    "outfit (null, если образ не нужен, иначе объект: title (string, название образа на русском), "
    "explanation (string, почему образ работает, на русском), score (number 0-100), "
    "comfort_score (number 0-100), item_ids (array of strings — ТОЛЬКО id вещей из списка гардероба)). "
    "Не выдумывай id. Никогда не оценивай лицо, тело или внешность."
)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def designer_chat(self: Any, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ai_analysis_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required for designer chat in API mode.")

    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("Designer chat message is required.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GarmentItem)
                .where(GarmentItem.user_id == UUID(user_id), GarmentItem.deleted_at.is_(None))
                .order_by(GarmentItem.updated_at.desc())
                .limit(40)
            )
            items = list(result.scalars())
            wardrobe_payload = [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "category": item.category,
                    "season": item.season,
                    "color": item.main_color,
                }
                for item in items
            ]

            context_lines = [f"Гардероб пользователя ({len(items)} вещей): {wardrobe_payload}"]
            if payload.get("weather_context"):
                context_lines.append(f"Погода сегодня: {payload['weather_context']}")
            if payload.get("preferences"):
                context_lines.append(f"Личные предпочтения пользователя: {payload['preferences']}")
            if payload.get("scenario"):
                context_lines.append(f"Сценарий дня: {payload['scenario']}")
            history = payload.get("history") or []
            for entry in history[-8:]:
                role = "Пользователь" if entry.get("role") == "user" else "Стилист"
                context_lines.append(f"{role} ранее: {entry.get('content', '')}")

            prompt = (
                DESIGNER_CHAT_SCHEMA_PROMPT
                + "\n\n"
                + "\n".join(context_lines)
                + f"\n\nСообщение пользователя: {message}"
            )
            gateway = LlmGateway(settings)
            generated = await gateway.generate_text_json(prompt, "DesignerChat")

            reply = str(generated.get("reply") or "Расскажите чуть подробнее, что планируете сегодня?")
            outfit_data = generated.get("outfit")
            outfit_id: str | None = None
            outfit_title: str | None = None
            if isinstance(outfit_data, dict) and items:
                selected_ids = {
                    UUID(str(item_id))
                    for item_id in outfit_data.get("item_ids", [])
                    if isinstance(item_id, str) and item_id
                }
                selected_items = [item for item in items if item.id in selected_ids]
                if selected_items:
                    outfit = OutfitCard(
                        user_id=UUID(user_id),
                        title=str(outfit_data.get("title") or "Образ дня"),
                        generation_context={
                            "source": "designer_chat",
                            "scenario": payload.get("scenario"),
                            "weather": payload.get("weather_context"),
                        },
                        designer_reasoning={
                            "provider": gateway.last_provider or settings.ai_analysis_provider,
                            "selected_item_count": len(selected_items),
                        },
                        explanation=str(outfit_data.get("explanation") or ""),
                        score=Decimal(str(outfit_data.get("score") or "75")),
                        comfort_score=Decimal(
                            str(outfit_data.get("comfort_score") or outfit_data.get("score") or "75")
                        ),
                    )
                    session.add(outfit)
                    await session.flush()
                    for item in selected_items:
                        session.add(OutfitItem(outfit_id=outfit.id, item_id=item.id, role=item.category))
                    outfit_id = str(outfit.id)
                    outfit_title = outfit.title
            session.add(
                AiRequest(
                    user_id=UUID(user_id),
                    task_id=UUID(outfit_id) if outfit_id else UUID(user_id),
                    provider=gateway.last_provider or settings.ai_analysis_provider,
                    model=gateway.last_model or settings.ai_analysis_model,
                    request_type="designer_chat",
                    status=ProcessingStatus.COMPLETED.value,
                    cost_usd=Decimal("0"),
                )
            )
            await session.commit()
            return {
                "reply": reply,
                "outfit_id": outfit_id,
                "outfit_title": outfit_title,
                "item_count": len(items),
            }

    logger.info("Designer chat for user hash %s", hash_identifier(user_id))
    started = time.perf_counter()
    result = run_worker_coroutine(run())
    logger.info(
        "Designer chat completed",
        extra={"user_id_hash": hash_identifier(user_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
    )
    return result


def _inline_image(content: bytes) -> str:
    content_type = detect_image_content_type(content) or "image/png"
    return f"data:{content_type};base64,{b64encode(content).decode()}"


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_avatar_image(self: Any, profile_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.image_generation_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required for avatar image generation.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            profile = await session.get(AvatarProfile, UUID(profile_id))
            if profile is None:
                raise ValueError("Avatar profile not found.")
            if profile.status == ProcessingStatus.COMPLETED.value and profile.generated_image_id:
                return {"profile_id": profile_id, "status": "already_completed"}
            if profile.consented_at is None or profile.revoked_at is not None or profile.reference_image_id is None:
                raise ValueError("Avatar consent or reference image is missing.")
            reference = await session.get(ImageAsset, profile.reference_image_id)
            if reference is None or reference.user_id != profile.user_id:
                raise ValueError("Avatar reference image not found.")
            measurement_result = await session.execute(
                select(AvatarMeasurement).where(AvatarMeasurement.avatar_profile_id == profile.id)
            )
            measurements = {
                measurement.code: f"{measurement.value} {measurement.unit}"
                for measurement in measurement_result.scalars()
            }
            profile.status = ProcessingStatus.PROCESSING.value
            profile.generation_error = None
            await session.commit()
            try:
                storage = ObjectStorage(settings)
                reference_content = await storage.get_bytes(reference.storage_key)
                prompt = (
                    "Create a respectful full-body virtual fitting avatar of the same adult person in the reference. "
                    "Preserve visible identity, height, build, and body proportions without slimming, beautifying, "
                    "or changing age, skin tone, disability, or body shape. Use a neutral warm-gray studio background, "
                    "front-facing relaxed stance, even soft lighting, and opaque fitted studio basics: a crew-neck "
                    "long-sleeve top and ankle-length leggings in matte medium gray. "
                    "The clothing must be non-revealing "
                    "and show the silhouette without sexualization. Do not add accessories or text. "
                    f"User-provided neutral description: {profile.description or 'none'}. "
                    f"User-provided measurements: {measurements or 'none'}."
                )
                output = await LlmGateway(settings).generate_composite_image(
                    [_inline_image(reference_content)],
                    prompt,
                )
                storage_key = build_storage_key(profile.user_id, "avatars", f"{profile.id}.png")
                await storage.put_bytes(storage_key, output, "image/png")
                generated = ImageAsset(
                    user_id=profile.user_id,
                    source_type="avatar",
                    storage_key=storage_key,
                    provenance_label=ProvenanceLabel.GENERATED_REFERENCE.value,
                    generated_prompt="Consented neutral avatar generation.",
                )
                session.add(generated)
                await session.flush()
                profile.generated_image_id = generated.id
                profile.status = ProcessingStatus.COMPLETED.value
                profile.generated_at = datetime.now(UTC)
                await finalize_billable_request(
                    session,
                    profile.user_id,
                    profile.id,
                    "generate_avatar",
                    settings.openrouter_model_image_gen,
                    ProcessingStatus.COMPLETED.value,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                await session.commit()
                return {"profile_id": profile_id, "status": ProcessingStatus.COMPLETED.value}
            except Exception as exc:
                profile.status = ProcessingStatus.FAILED.value
                profile.generation_error = exc.__class__.__name__
                await finalize_billable_request(
                    session,
                    profile.user_id,
                    profile.id,
                    "generate_avatar",
                    settings.openrouter_model_image_gen,
                    ProcessingStatus.FAILED.value,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error_code=exc.__class__.__name__,
                )
                await session.commit()
                raise

    started = time.perf_counter()
    result = run_worker_coroutine(run())
    logger.info(
        "Avatar generation completed",
        extra={
            "profile_id_hash": hash_identifier(profile_id),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return result


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_virtual_try_on(self: Any, job_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.image_generation_enabled:
        raise RuntimeError("OPENROUTER_API_KEY is required for virtual try-on image generation.")

    async def run() -> dict[str, Any]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            job = await session.get(TryOnJob, UUID(job_id))
            if job is None:
                raise ValueError("Try-on job not found.")
            if job.status == ProcessingStatus.COMPLETED.value and job.output_image_id:
                return {"job_id": job_id, "status": "already_completed"}
            profile = await session.get(AvatarProfile, job.avatar_profile_id)
            if profile is None or profile.generated_image_id is None or profile.revoked_at is not None:
                raise ValueError("Generated avatar is unavailable.")
            avatar_image = await session.get(ImageAsset, profile.generated_image_id)
            if avatar_image is None or avatar_image.user_id != job.user_id:
                raise ValueError("Generated avatar image is unavailable.")
            item_result = await session.execute(
                select(TryOnItem, GarmentItem)
                .join(GarmentItem, GarmentItem.id == TryOnItem.item_id)
                .where(TryOnItem.try_on_job_id == job.id, GarmentItem.user_id == job.user_id)
                .order_by(TryOnItem.sort_order)
            )
            garment_rows = list(item_result.all())
            if not garment_rows:
                raise ValueError("Try-on garments are unavailable.")
            job.status = ProcessingStatus.PROCESSING.value
            job.error_code = None
            job.error_message = None
            await session.commit()
            try:
                storage = ObjectStorage(settings)
                source_urls = [_inline_image(await storage.get_bytes(avatar_image.storage_key))]
                garment_titles: list[str] = []
                for _, garment in garment_rows:
                    image_id = garment.processed_image_id or garment.original_image_id
                    image = await session.get(ImageAsset, image_id) if image_id else None
                    if image is None or image.user_id != job.user_id:
                        raise ValueError(f"Garment image unavailable for item {garment.id}.")
                    source_urls.append(_inline_image(await storage.get_bytes(image.storage_key)))
                    garment_titles.append(garment.title)
                prompt = (
                    "The first image is a consented full-body avatar. The remaining images are garment references. "
                    "Dress the same avatar in exactly those garments while preserving face, identity, height, build, "
                    "body proportions, pose, camera, and neutral background. Do not slim, reshape, beautify, or expose "
                    "the body. Keep realistic layering and fabric boundaries. Return one full-body fitting preview "
                    f"without text. Garments: {garment_titles}."
                )
                output = await LlmGateway(settings).generate_composite_image(source_urls, prompt)
                storage_key = build_storage_key(job.user_id, "try-ons", f"{job.id}.png")
                await storage.put_bytes(storage_key, output, "image/png")
                generated = ImageAsset(
                    user_id=job.user_id,
                    source_type="try_on",
                    storage_key=storage_key,
                    provenance_label=ProvenanceLabel.GENERATED_REFERENCE.value,
                    generated_prompt="Consented virtual try-on generation.",
                )
                session.add(generated)
                await session.flush()
                job.output_image_id = generated.id
                job.status = ProcessingStatus.COMPLETED.value
                job.completed_at = datetime.now(UTC)
                await finalize_billable_request(
                    session,
                    job.user_id,
                    job.id,
                    "virtual_try_on",
                    settings.openrouter_model_image_gen,
                    ProcessingStatus.COMPLETED.value,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                await session.commit()
                return {"job_id": job_id, "status": ProcessingStatus.COMPLETED.value}
            except Exception as exc:
                job.status = ProcessingStatus.FAILED.value
                job.error_code = exc.__class__.__name__
                job.error_message = "Virtual try-on generation failed."
                job.completed_at = datetime.now(UTC)
                await finalize_billable_request(
                    session,
                    job.user_id,
                    job.id,
                    "virtual_try_on",
                    settings.openrouter_model_image_gen,
                    ProcessingStatus.FAILED.value,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error_code=exc.__class__.__name__,
                )
                await session.commit()
                raise

    started = time.perf_counter()
    result = run_worker_coroutine(run())
    logger.info(
        "Virtual try-on completed",
        extra={"job_id_hash": hash_identifier(job_id), "duration_ms": int((time.perf_counter() - started) * 1000)},
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
    return run_worker_coroutine(run())

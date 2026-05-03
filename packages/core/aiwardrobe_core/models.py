from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from aiwardrobe_core.db import Base
from aiwardrobe_core.enums import (
    AvailabilityStatus,
    GarmentStatus,
    PaymentProviderCode,
    PaymentStatus,
    PrivacyMode,
    ProcessingStatus,
    ProvenanceLabel,
    SubscriptionPlan,
    UploadSource,
    UploadType,
    UserRole,
)


JsonDict = dict[str, Any]
JsonList = list[Any]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(16), default="ru")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    city: Mapped[str | None] = mapped_column(String(255))
    location_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location_lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    wardrobe_mode: Mapped[str] = mapped_column(String(64), default="personal")
    preferred_styles: Mapped[JsonList] = mapped_column(JSONB, default=list)
    disliked_styles: Mapped[JsonList] = mapped_column(JSONB, default=list)
    preferred_colors: Mapped[JsonList] = mapped_column(JSONB, default=list)
    disliked_colors: Mapped[JsonList] = mapped_column(JSONB, default=list)
    dress_code: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    notification_time: Mapped[time | None] = mapped_column(Time)
    privacy_mode: Mapped[str] = mapped_column(String(32), default=PrivacyMode.STANDARD.value)
    allow_ai_processing: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_research: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_training: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_plan: Mapped[str] = mapped_column(String(32), default=SubscriptionPlan.FREE.value)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.USER.value)


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_hash: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    license_status: Mapped[str] = mapped_column(String(64), default="private")
    provenance_label: Mapped[str] = mapped_column(
        String(64), default=ProvenanceLabel.USER_PROCESSED.value
    )
    generated_prompt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Upload(Base, TimestampMixin):
    __tablename__ = "uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), default=UploadSource.MINIAPP.value)
    upload_type: Mapped[str] = mapped_column(String(32), default=UploadType.AUTO.value)
    telegram_file_id: Mapped[str | None] = mapped_column(String(512))
    original_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    status: Mapped[str] = mapped_column(String(32), default=ProcessingStatus.CREATED.value)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GarmentItem(Base, TimestampMixin):
    __tablename__ = "garment_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(128), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    main_color: Mapped[str | None] = mapped_column(String(128))
    secondary_colors: Mapped[JsonList] = mapped_column(JSONB, default=list)
    color_temperature: Mapped[str | None] = mapped_column(String(64))
    palette_role: Mapped[str | None] = mapped_column(String(64))
    brightness: Mapped[str | None] = mapped_column(String(64))
    saturation: Mapped[str | None] = mapped_column(String(64))
    pattern: Mapped[str | None] = mapped_column(String(128))
    material_guess: Mapped[str | None] = mapped_column(String(128))
    silhouette: Mapped[str | None] = mapped_column(String(128))
    fit: Mapped[str | None] = mapped_column(String(128))
    visual_weight: Mapped[str | None] = mapped_column(String(128))
    texture: Mapped[str | None] = mapped_column(String(128))
    season: Mapped[JsonList] = mapped_column(JSONB, default=list)
    temperature_min: Mapped[int | None]
    temperature_max: Mapped[int | None]
    formality_level: Mapped[int | None]
    style_archetype: Mapped[JsonList] = mapped_column(JSONB, default=list)
    occasion_fit: Mapped[JsonList] = mapped_column(JSONB, default=list)
    designer_attributes: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    styling_logic: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    research_summary: Mapped[str | None] = mapped_column(Text)
    research_sources: Mapped[JsonList] = mapped_column(JSONB, default=list)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    status: Mapped[str] = mapped_column(String(32), default=GarmentStatus.DRAFT.value)
    availability_status: Mapped[str] = mapped_column(String(64), default=AvailabilityStatus.AVAILABLE.value)
    source_upload_id: Mapped[UUID | None] = mapped_column(ForeignKey("uploads.id"))
    source_look_id: Mapped[UUID | None] = mapped_column(ForeignKey("look_cards.id"))
    original_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    processed_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    thumbnail_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    wear_count: Mapped[int] = mapped_column(default=0)
    last_worn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LookCard(Base, TimestampMixin):
    __tablename__ = "look_cards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    source_upload_id: Mapped[UUID | None] = mapped_column(ForeignKey("uploads.id"))
    original_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    preview_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    style_tags: Mapped[JsonList] = mapped_column(JSONB, default=list)
    season: Mapped[JsonList] = mapped_column(JSONB, default=list)
    weather_fit: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    color_palette: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    designer_reasoning: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["LookItem"]] = relationship(back_populates="look")


class LookItem(Base):
    __tablename__ = "look_items"

    look_id: Mapped[UUID] = mapped_column(ForeignKey("look_cards.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("garment_items.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(default=0)
    look: Mapped[LookCard] = relationship(back_populates="items")


class OutfitCard(Base, TimestampMixin):
    __tablename__ = "outfit_cards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    generation_context: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    weather_snapshot: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    designer_reasoning: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    comfort_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    outfit_dna: Mapped[str | None] = mapped_column(Text)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    user_rating: Mapped[str | None] = mapped_column(String(32))
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["OutfitItem"]] = relationship(back_populates="outfit")


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    outfit_id: Mapped[UUID] = mapped_column(
        ForeignKey("outfit_cards.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("garment_items.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(64))
    outfit: Mapped[OutfitCard] = relationship(back_populates="items")


class AiRequest(Base):
    __tablename__ = "ai_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(64), default="openrouter")
    model: Mapped[str] = mapped_column(String(255))
    request_type: Mapped[str] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventContext(Base):
    __tablename__ = "event_contexts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    formality_min: Mapped[int] = mapped_column(default=0)
    formality_max: Mapped[int] = mapped_column(default=10)
    comfort_priority: Mapped[int] = mapped_column(default=5)
    walking_level: Mapped[int] = mapped_column(default=0)
    sitting_level: Mapped[int] = mapped_column(default=0)
    weather_exposure: Mapped[int] = mapped_column(default=0)
    layering_importance: Mapped[int] = mapped_column(default=0)
    shoe_comfort_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_style_tags: Mapped[JsonList] = mapped_column(JSONB, default=list)
    avoid_rules: Mapped[JsonList] = mapped_column(JSONB, default=list)


class OutfitGenerationRequest(Base):
    __tablename__ = "outfit_generation_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    anchor_item_ids: Mapped[JsonList] = mapped_column(JSONB, default=list)
    weather_mode: Mapped[str] = mapped_column(String(64), default="auto")
    manual_weather: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    time_context: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    event_type: Mapped[str | None] = mapped_column(String(64))
    creativity: Mapped[int] = mapped_column(default=5)
    variants_count: Mapped[int] = mapped_column(default=3)
    prompt: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=ProcessingStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketplaceResult(Base):
    __tablename__ = "marketplace_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[UUID | None]
    marketplace: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    reviews_count: Mapped[int | None]
    match_reason: Mapped[str | None] = mapped_column(Text)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    availability_status: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MissingItemCard(Base):
    __tablename__ = "missing_item_cards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    designer_role: Mapped[str | None] = mapped_column(String(128))
    colors: Mapped[JsonList] = mapped_column(JSONB, default=list)
    season: Mapped[JsonList] = mapped_column(JSONB, default=list)
    style_tags: Mapped[JsonList] = mapped_column(JSONB, default=list)
    priority: Mapped[int] = mapped_column(default=0)
    generated_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    marketplace_result_ids: Mapped[JsonList] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WishlistItem(Base, TimestampMixin):
    __tablename__ = "wishlist_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    marketplace_result_id: Mapped[UUID | None] = mapped_column(ForeignKey("marketplace_results.id"))
    status: Mapped[str] = mapped_column(String(64), default="idea")
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[JsonList] = mapped_column(JSONB, default=list)


class StyleDna(Base):
    __tablename__ = "style_dna"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    dominant_styles: Mapped[JsonList] = mapped_column(JSONB, default=list)
    avoided_styles: Mapped[JsonList] = mapped_column(JSONB, default=list)
    preferred_color_families: Mapped[JsonList] = mapped_column(JSONB, default=list)
    avoided_color_families: Mapped[JsonList] = mapped_column(JSONB, default=list)
    preferred_silhouettes: Mapped[JsonList] = mapped_column(JSONB, default=list)
    preferred_formality_range: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    comfort_priority: Mapped[int] = mapped_column(default=5)
    practicality_level: Mapped[int] = mapped_column(default=5)
    expressiveness_level: Mapped[int] = mapped_column(default=5)
    minimalism_level: Mapped[int] = mapped_column(default=5)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserStyleRule(Base):
    __tablename__ = "user_style_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    natural_language_rule: Mapped[str] = mapped_column(Text)
    parsed_rule: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutfitMemory(Base):
    __tablename__ = "outfit_memories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    outfit_id: Mapped[UUID] = mapped_column(ForeignKey("outfit_cards.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    context: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WardrobeHealthSnapshot(Base):
    __tablename__ = "wardrobe_health_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    coverage_by_season: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    coverage_by_event: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    missing_roles: Mapped[JsonList] = mapped_column(JSONB, default=list)
    duplicate_groups: Mapped[JsonList] = mapped_column(JSONB, default=list)
    orphan_items: Mapped[JsonList] = mapped_column(JSONB, default=list)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrivacyReceipt(Base):
    __tablename__ = "privacy_receipts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[UUID] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), index=True)
    ai_provider_used: Mapped[str] = mapped_column(String(64), default="openrouter")
    model_used: Mapped[str] = mapped_column(String(255))
    original_saved: Mapped[bool] = mapped_column(Boolean, default=True)
    research_used: Mapped[bool] = mapped_column(Boolean, default=False)
    training_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_original_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseSimulation(Base):
    __tablename__ = "purchase_simulations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_image_id: Mapped[UUID | None] = mapped_column(ForeignKey("image_assets.id"))
    product_description: Mapped[str] = mapped_column(Text)
    buy_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    duplicate_risk: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    compatibility_count: Mapped[int] = mapped_column(default=0)
    scenario_coverage: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    recommendation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationSetting(Base, TimestampMixin):
    __tablename__ = "notification_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    morning_time: Mapped[time | None] = mapped_column(Time)
    weekdays: Mapped[JsonList] = mapped_column(JSONB, default=list)
    quiet_hours: Mapped[JsonDict] = mapped_column(JSONB, default=dict)
    bad_weather_only: Mapped[bool] = mapped_column(Boolean, default=False)
    events_only: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_disabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(32), default=SubscriptionPlan.FREE.value)
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_period_start: Mapped[date | None] = mapped_column(Date)
    current_period_end: Mapped[date | None] = mapped_column(Date)
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255))


class UsageLimit(Base, TimestampMixin):
    __tablename__ = "usage_limits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(32), default=SubscriptionPlan.FREE.value)
    period: Mapped[str] = mapped_column(String(16), default="month")
    item_limit: Mapped[int]
    ai_analysis_limit: Mapped[int]
    item_count: Mapped[int] = mapped_column(default=0)
    ai_analysis_count: Mapped[int] = mapped_column(default=0)
    resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default=PaymentProviderCode.TELEGRAM.value)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.PENDING.value)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    plan: Mapped[str] = mapped_column(String(32))
    raw_event: Mapped[JsonDict] = mapped_column(JSONB, default=dict)


Index("ix_items_user_category_status", GarmentItem.user_id, GarmentItem.category, GarmentItem.status)
Index("ix_ai_requests_user_created", AiRequest.user_id, AiRequest.created_at)
Index("ix_uploads_user_status", Upload.user_id, Upload.status)

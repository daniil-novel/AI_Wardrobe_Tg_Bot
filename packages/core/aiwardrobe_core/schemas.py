from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ApiError(BaseModel):
    detail: str
    code: str = "error"


class HealthResponse(BaseModel):
    status: str
    app_env: str
    missing_runtime_secrets: list[str]


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    language: str
    timezone: str
    city: str | None = None
    subscription_plan: str
    privacy_mode: str


class UploadInitRequest(BaseModel):
    upload_type: str = "auto"
    content_type: str = "image/jpeg"
    filename: str


class UploadInitResponse(BaseModel):
    upload_id: UUID
    storage_key: str
    signed_url: str
    expires_in_seconds: int


class UploadCompleteRequest(BaseModel):
    upload_id: UUID
    storage_key: str


class TelegramUploadRequest(BaseModel):
    telegram_file_id: str
    upload_type: str = "auto"


class UploadStatus(BaseModel):
    id: UUID
    status: str
    task_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ImageAssetRead(BaseModel):
    id: UUID
    storage_key: str
    provenance_label: str


class GarmentItemRead(BaseModel):
    id: UUID
    title: str
    category: str
    season: list[Any] = Field(default_factory=list)
    main_color: str | None = None
    confidence: Decimal = Decimal("0")
    status: str
    availability_status: str
    designer_attributes: dict[str, Any] = Field(default_factory=dict)


class GarmentItemUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    season: list[str] | None = None
    status: str | None = None
    availability_status: str | None = None
    designer_attributes: dict[str, Any] | None = None


class LookCardRead(BaseModel):
    id: UUID
    title: str
    is_favorite: bool
    style_tags: list[Any] = Field(default_factory=list)
    designer_reasoning: dict[str, Any] = Field(default_factory=dict)
    confidence: Decimal = Decimal("0")


class OutfitRequest(BaseModel):
    prompt: str | None = None
    anchor_item_ids: list[UUID] = Field(default_factory=list)
    weather: dict[str, Any] = Field(default_factory=dict)
    event_type: str | None = None
    variants_count: int = Field(default=3, ge=1, le=5)


class OutfitRead(BaseModel):
    id: UUID
    title: str
    score: Decimal = Decimal("0")
    comfort_score: Decimal | None = None
    explanation: str | None = None
    designer_reasoning: dict[str, Any] = Field(default_factory=dict)
    is_favorite: bool = False


class AiTaskRequest(BaseModel):
    upload_id: UUID
    task_type: str = "analyze_image"


class AiTaskStatus(BaseModel):
    task_id: str
    status: str


class MarketplaceSearchRequest(BaseModel):
    query: str
    source_item_id: UUID | None = None
    marketplaces: list[str] = Field(default_factory=lambda: ["ozon", "wildberries"])


class MarketplaceResultRead(BaseModel):
    id: UUID
    marketplace: str
    title: str
    url: HttpUrl
    price: Decimal | None = None
    match_confidence: Decimal | None = None
    trust_label: str = "Проверьте цену и наличие"


class WishlistCreate(BaseModel):
    title: str
    source_url: HttpUrl | None = None
    notes: str | None = None


class WishlistRead(BaseModel):
    id: UUID
    title: str
    source_url: str | None = None
    status: str
    notes: str | None = None


class StyleDnaRead(BaseModel):
    dominant_styles: list[Any] = Field(default_factory=list)
    avoided_styles: list[Any] = Field(default_factory=list)
    preferred_color_families: list[Any] = Field(default_factory=list)
    avoided_color_families: list[Any] = Field(default_factory=list)
    preferred_silhouettes: list[Any] = Field(default_factory=list)
    preferred_formality_range: dict[str, Any] = Field(default_factory=dict)
    confidence: Decimal = Decimal("0")


class StyleRuleCreate(BaseModel):
    natural_language_rule: str


class StyleRuleRead(BaseModel):
    id: UUID
    natural_language_rule: str
    parsed_rule: dict[str, Any] = Field(default_factory=dict)
    enabled: bool


class WardrobeHealthRead(BaseModel):
    score: Decimal = Decimal("0")
    coverage_by_season: dict[str, Any] = Field(default_factory=dict)
    coverage_by_event: dict[str, Any] = Field(default_factory=dict)
    missing_roles: list[Any] = Field(default_factory=list)
    duplicate_groups: list[Any] = Field(default_factory=list)
    orphan_items: list[Any] = Field(default_factory=list)


class PrivacyReceiptRead(BaseModel):
    upload_id: UUID
    ai_provider_used: str
    model_used: str
    original_saved: bool
    research_used: bool
    training_allowed: bool
    deleted_original_at: datetime | None = None


class PurchaseSimulationRequest(BaseModel):
    product_description: str
    source_url: HttpUrl | None = None


class PurchaseSimulationRead(BaseModel):
    buy_score: Decimal
    duplicate_risk: Decimal
    compatibility_count: int
    scenario_coverage: dict[str, Any]
    recommendation: str


class PlanRead(BaseModel):
    code: str
    item_limit: int | None
    ai_analysis_limit: int | None
    features: list[str]

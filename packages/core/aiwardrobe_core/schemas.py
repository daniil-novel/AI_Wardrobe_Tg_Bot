from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ApiError(BaseModel):
    detail: str
    code: str = "error"


class HealthResponse(BaseModel):
    status: str
    app_env: str
    missing_runtime_secrets: list[str]
    ai_execution_mode: str
    ai_analysis_provider: str
    image_generation_provider: str


class RootResponse(BaseModel):
    name: str
    version: str
    status: str
    docs_url: str
    health_url: str
    miniapp_url: str
    api_groups: list[str]


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


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
    telegram_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    language: str = "ru"
    upload_type: str = "auto"


class UploadStatus(BaseModel):
    id: UUID
    status: str
    task_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    filename: str | None = None
    upload_type: str | None = None
    progress: int = 0
    result_title: str | None = None


class UploadSelectionPayload(BaseModel):
    """Normalized crop metadata; the client sends only pixels inside this region."""

    kind: Literal["full", "rectangle"] = "full"
    source: Literal["default", "user"] = "default"
    x: float = Field(default=0, ge=0, le=1)
    y: float = Field(default=0, ge=0, le=1)
    width: float = Field(default=1, gt=0, le=1)
    height: float = Field(default=1, gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "UploadSelectionPayload":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Selection must stay inside normalized image bounds.")
        return self


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
    item_ids: list[UUID] = Field(default_factory=list)


class OutfitRequest(BaseModel):
    prompt: str | None = None
    anchor_item_ids: list[UUID] = Field(default_factory=list)
    weather: dict[str, Any] = Field(default_factory=dict)
    event_type: str | None = None
    variants_count: int = Field(default=3, ge=1, le=5)


class DesignerChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    scenario: str | None = None
    preferences: str | None = None
    weather_context: str | None = None


class DesignerChatResponse(BaseModel):
    reply: str
    outfit_id: UUID | None = None
    outfit_title: str | None = None
    outfit_explanation: str | None = None
    outfit_score: float | None = None
    outfit_item_ids: list[UUID] = Field(default_factory=list)
    item_count: int = 0


class OutfitRead(BaseModel):
    id: UUID
    title: str
    score: Decimal = Decimal("0")
    comfort_score: Decimal | None = None
    explanation: str | None = None
    designer_reasoning: dict[str, Any] = Field(default_factory=dict)
    is_favorite: bool = False
    item_ids: list[UUID] = Field(default_factory=list)


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
    title: str
    monthly_price: Decimal
    currency: str
    item_limit: int | None
    ai_analysis_limit: int | None
    avatar_generation_limit: int
    try_on_limit: int
    features: list[str]
    pricing_status: str


class BillingAccessRead(BaseModel):
    enabled: bool
    payments_enabled: bool
    plan: str
    source: str
    expires_at: datetime | None
    features: list[str]


class PromoRedeemRequest(BaseModel):
    code: str = Field(min_length=8, max_length=128)


class PromoRedeemRead(BaseModel):
    plan: str
    expires_at: datetime
    features: list[str]


class AvatarMeasurementWrite(BaseModel):
    code: Literal["height", "shoulders", "chest", "waist", "hips", "inseam"]
    value: Decimal = Field(gt=0, le=300)
    unit: Literal["cm"] = "cm"


class AvatarMeasurementRead(AvatarMeasurementWrite):
    source: str
    confidence: Decimal | None = None


class AvatarProfileUpdate(BaseModel):
    consent: bool
    consent_version: str = Field(default="2026-07", max_length=32)
    description: str | None = Field(default=None, max_length=2000)
    neutral_clothing: Literal["fitted_studio_basics"] = "fitted_studio_basics"
    reference_upload_id: UUID | None = None
    measurements: list[AvatarMeasurementWrite] = Field(default_factory=list, max_length=6)


class AvatarProfileRead(BaseModel):
    id: UUID
    status: str
    description: str | None
    neutral_clothing: str
    reference_image_id: UUID | None
    generated_image_id: UUID | None
    consent_version: str | None
    consented_at: datetime | None
    revoked_at: datetime | None
    generation_error: str | None
    generated_at: datetime | None
    measurements: list[AvatarMeasurementRead]


class TryOnCreate(BaseModel):
    garment_item_ids: list[UUID] = Field(min_length=1, max_length=8)


class TryOnRead(BaseModel):
    id: UUID
    status: str
    provider: str | None
    output_image_id: UUID | None
    error_code: str | None
    error_message: str | None
    garment_item_ids: list[UUID]
    created_at: datetime
    completed_at: datetime | None

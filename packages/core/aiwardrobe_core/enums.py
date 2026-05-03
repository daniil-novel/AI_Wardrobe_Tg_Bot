from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    STYLIST = "stylist"


class SubscriptionPlan(StrEnum):
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class PrivacyMode(StrEnum):
    STANDARD = "standard"
    PRIVATE = "private"
    MINIMAL = "minimal"


class UploadSource(StrEnum):
    TELEGRAM = "telegram"
    MINIAPP = "miniapp"


class UploadType(StrEnum):
    ITEM = "item"
    LOOK = "look"
    PRODUCT_SCREENSHOT = "product_screenshot"
    AUTO = "auto"


class ProcessingStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    NEEDS_CONFIRMATION = "needs_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImageAssetType(StrEnum):
    ORIGINAL = "original"
    PROCESSED = "processed"
    THUMBNAIL = "thumbnail"
    GENERATED_REFERENCE = "generated_reference"
    EXTERNAL_PRODUCT_PHOTO = "external_product_photo"
    SHARE_CARD = "share_card"


class ProvenanceLabel(StrEnum):
    USER_PROCESSED = "user_processed"
    EXTERNAL_PRODUCT_PHOTO = "external_product_photo"
    GENERATED_REFERENCE = "generated_reference"
    PLACEHOLDER = "placeholder"


class GarmentStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    LAUNDRY = "laundry"
    DRYING = "drying"
    REPAIR = "repair"
    DIRTY_BUT_WEARABLE = "dirty_but_wearable"
    NOT_NOW = "not_now"
    OUT_OF_SEASON = "out_of_season"
    SOLD_OR_GIVEN_AWAY = "sold_or_given_away"
    ARCHIVED = "archived"


class PaymentProviderCode(StrEnum):
    TELEGRAM = "telegram"
    EXTERNAL = "external"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

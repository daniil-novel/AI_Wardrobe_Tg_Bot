# Architecture

## System Diagram

```mermaid
flowchart LR
    tg[Telegram clients] --> bot[aiogram bot]
    tg --> mini[React Telegram Mini App]
    mini --> api[FastAPI API]
    bot --> api
    api --> pg[(PostgreSQL)]
    api --> s3[(S3 compatible private storage)]
    api --> broker[(Redis / RabbitMQ broker)]
    broker --> worker[Celery workers]
    worker --> pg
    worker --> s3
    worker --> openrouter[OpenRouter LLM API]
    api --> redis[(Redis cache / result backend)]
    worker --> redis
    api --> logs[JSON logs / metrics]
    worker --> logs
```

## Containers

- **Telegram Bot** receives commands/photos and delegates business work to the backend.
- **Mini App** is the primary mobile-first UI inside Telegram WebView.
- **FastAPI API** owns auth, DTOs, domain orchestration and public HTTP contracts.
- **Celery Workers** own image analysis, OpenRouter calls, research, recommendations and notifications.
- **PostgreSQL** stores relational domain data and JSONB designer attributes.
- **Redis** stores Celery queues, rate-limit counters, short task state and idempotency keys.
- **S3-compatible storage** stores private originals, processed images, thumbnails, generated references and share cards.
- **RabbitMQ** is recommended as the production Celery broker when durable delivery and broker observability matter.

## Domain Boundaries

- Telegram handlers never contain wardrobe business logic.
- API schemas are Pydantic DTOs and remain separate from SQLAlchemy ORM models.
- LLM Gateway is the only OpenRouter boundary and is responsible for model IDs, retries, JSON validation and cost accounting hooks.
- Payment integrations are adapters behind a provider-neutral billing layer.

## AI Pipeline

1. User uploads an image through bot or Mini App.
2. Backend stores original image metadata and creates an upload task.
3. Worker receives a signed read URL with short TTL.
4. LLM Gateway calls OpenRouter with safe clothing-only prompts.
5. JSON response is validated against Pydantic schemas.
6. Backend persists garment/look/outfit records and privacy receipt.
7. Bot notification or Mini App status view surfaces the result.

Research must use only text extracted from the item description. Private photos, face data and body assessment are out of bounds.

## Scaling

- API and LLM Gateway are stateless and horizontally scalable.
- Workers scale by queue: `ai`, `research`, `recommendations`, `notifications`.
- PostgreSQL can move to primary + read replica.
- Redis can move to a managed cluster.
- Object storage can move from MinIO to any S3-compatible provider.

## Broker Decision

Redis remains required for cache-like state, task results and low-latency counters. RabbitMQ is a better production broker
for Celery queues because it gives durable queues, acknowledgements and clearer queue operations. Kafka is not recommended
for the current v0.2.2 scope: the product needs command-style background jobs, not high-throughput immutable event streams.
Kafka should be revisited only after an outbox/event-ledger requirement appears for analytics, marketplace ingestion or
multi-service synchronization.

## Database Schema

```mermaid
erDiagram
    users {
        uuid id PK
        bigint telegram_id UK
        text telegram_username
        text first_name
        text language
        text timezone
        text city
        text subscription_plan
        text privacy_mode
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    roles {
        uuid id PK
        text code UK
        text description
    }

    sessions {
        uuid id PK
        uuid user_id FK
        text refresh_token_hash UK
        text user_agent
        text ip_hash
        timestamp expires_at
        timestamp revoked_at
    }

    image_assets {
        uuid id PK
        uuid user_id FK
        text storage_key UK
        text content_type
        bigint size_bytes
        text provenance_label
        text checksum_sha256
        timestamp deleted_at
    }

    uploads {
        uuid id PK
        uuid user_id FK
        uuid original_image_id FK
        text upload_type
        text filename
        text status
        text error_code
        text error_message
        numeric confidence
        timestamp completed_at
    }

    garment_items {
        uuid id PK
        uuid user_id FK
        uuid source_upload_id FK
        uuid original_image_id FK
        text title
        text category
        text main_color
        jsonb season
        jsonb style_archetype
        jsonb designer_attributes
        text status
        text availability_status
        numeric confidence
    }

    look_cards {
        uuid id PK
        uuid user_id FK
        uuid source_upload_id FK
        text title
        jsonb style_tags
        jsonb designer_reasoning
        numeric confidence
        boolean is_favorite
    }

    look_items {
        uuid look_id FK
        uuid item_id FK
        text role
    }

    outfit_cards {
        uuid id PK
        uuid user_id FK
        text title
        jsonb generation_context
        jsonb designer_reasoning
        numeric score
        numeric comfort_score
        boolean is_favorite
    }

    outfit_items {
        uuid outfit_id FK
        uuid item_id FK
        text role
    }

    ai_requests {
        uuid id PK
        uuid user_id FK
        uuid task_id
        text model
        text request_type
        text status
        numeric cost_usd
        text error_code
        timestamp created_at
    }

    event_contexts {
        uuid id PK
        uuid user_id FK
        text event_type
        text dress_code
        jsonb weather
        timestamp starts_at
    }

    outfit_generation_requests {
        uuid id PK
        uuid user_id FK
        uuid outfit_id FK
        jsonb anchor_item_ids
        jsonb context_payload
        text status
    }

    marketplace_results {
        uuid id PK
        uuid user_id FK
        uuid source_item_id FK
        text marketplace
        text title
        text url
        numeric price
        numeric match_confidence
        text trust_label
    }

    missing_item_cards {
        uuid id PK
        uuid user_id FK
        text title
        text category
        text priority
        jsonb reasoning
    }

    wishlist_items {
        uuid id PK
        uuid user_id FK
        text title
        text source_url
        text status
        text notes
    }

    style_dna {
        uuid user_id PK
        jsonb dominant_styles
        jsonb avoided_styles
        jsonb preferred_color_families
        jsonb avoided_color_families
        numeric confidence
    }

    user_style_rules {
        uuid id PK
        uuid user_id FK
        text natural_language_rule
        jsonb parsed_rule
        boolean enabled
    }

    outfit_memories {
        uuid id PK
        uuid user_id FK
        uuid outfit_id FK
        text feedback
        jsonb context
    }

    wardrobe_health_snapshots {
        uuid id PK
        uuid user_id FK
        numeric score
        jsonb coverage_by_season
        jsonb coverage_by_event
        jsonb missing_roles
        jsonb duplicate_groups
    }

    privacy_receipts {
        uuid id PK
        uuid user_id FK
        uuid upload_id FK
        text ai_provider_used
        text model_used
        boolean original_saved
        boolean research_used
        boolean training_allowed
    }

    purchase_simulations {
        uuid id PK
        uuid user_id FK
        text product_description
        text source_url
        numeric buy_score
        numeric duplicate_risk
        integer compatibility_count
        jsonb scenario_coverage
        text recommendation
    }

    notification_settings {
        uuid id PK
        uuid user_id FK
        text channel
        boolean enabled
        jsonb preferences
    }

    subscriptions {
        uuid id PK
        uuid user_id FK
        text plan
        text status
        timestamp active_until
    }

    usage_limits {
        uuid id PK
        uuid user_id FK
        text period_key
        integer item_count
        integer ai_analysis_count
    }

    payments {
        uuid id PK
        uuid user_id FK
        uuid subscription_id FK
        text provider
        text provider_payment_id
        text status
        numeric amount
        text currency
    }

    users ||--o{ sessions : owns
    users ||--o{ image_assets : owns
    users ||--o{ uploads : creates
    image_assets ||--o{ uploads : original
    uploads ||--o{ garment_items : source
    uploads ||--o{ look_cards : source
    users ||--o{ garment_items : owns
    users ||--o{ look_cards : owns
    garment_items ||--o{ look_items : used_by
    look_cards ||--o{ look_items : contains
    users ||--o{ outfit_cards : owns
    garment_items ||--o{ outfit_items : used_by
    outfit_cards ||--o{ outfit_items : contains
    users ||--o{ ai_requests : requests
    users ||--o{ event_contexts : plans
    users ||--o{ outfit_generation_requests : asks
    outfit_cards ||--o{ outfit_generation_requests : result
    users ||--o{ marketplace_results : sees
    garment_items ||--o{ marketplace_results : source
    users ||--o{ missing_item_cards : needs
    users ||--o{ wishlist_items : saves
    users ||--|| style_dna : has
    users ||--o{ user_style_rules : defines
    users ||--o{ outfit_memories : remembers
    outfit_cards ||--o{ outfit_memories : feedback
    users ||--o{ wardrobe_health_snapshots : receives
    users ||--o{ privacy_receipts : owns
    uploads ||--o{ privacy_receipts : documents
    users ||--o{ purchase_simulations : runs
    users ||--o{ notification_settings : configures
    users ||--o{ subscriptions : pays_for
    users ||--o{ usage_limits : consumes
    subscriptions ||--o{ payments : paid_by
```

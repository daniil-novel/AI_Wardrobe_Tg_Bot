# Architecture

## Containers

- **Telegram Bot** receives commands/photos and delegates business work to the backend.
- **Mini App** is the primary mobile-first UI inside Telegram WebView.
- **FastAPI API** owns auth, DTOs, domain orchestration and public HTTP contracts.
- **Celery Workers** own image analysis, OpenRouter calls, research, recommendations and notifications.
- **PostgreSQL** stores relational domain data and JSONB designer attributes.
- **Redis** stores Celery queues, rate-limit counters, short task state and idempotency keys.
- **S3-compatible storage** stores private originals, processed images, thumbnails, generated references and share cards.

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

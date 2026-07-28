# Architecture Decision Records

## ADR-001: Python FastAPI + aiogram

Chosen to satisfy the Python-first requirement and keep Bot API, backend and workers in one typed ecosystem.

## ADR-002: React + TypeScript Mini App

Chosen because the UI spec requires a rich mobile-first Telegram WebView with multiple stateful screens, progressive disclosure and design tokens.

## ADR-003: Celery + Redis

Chosen to keep OpenRouter/image/research work outside the API and bot event loops. Queue names map to scaling boundaries.

## ADR-004: S3-compatible image storage

Chosen because images must remain private and must not be stored as PostgreSQL binary blobs. MinIO is used locally, S3-compatible providers in production.

## ADR-005: Billing adapter layer

Chosen to support Telegram Payments and external providers without hard-coding payment logic into wardrobe services.

## ADR-006: Hybrid AI execution with capability boundaries

Garment recognition and JSON text inference may use OpenRouter, an isolated local `codex exec` runner, or an ordered
hybrid fallback. The server places bounded-TTL jobs in Redis; a trusted workstation claims and completes them through
bearer-authenticated outbound HTTPS. No workstation inbound port is opened and Codex credentials never enter the VPS
or its images. Codex receives private images only as short-lived local files in an empty temporary directory; prompts
travel over stdin, user configuration/rules are ignored, the sandbox is read-only, and unrelated application secrets
are stripped from the child environment.

Pixel generation is a separate capability. Product cards, avatars and virtual try-on continue to use the configured
OpenRouter image-generation model because Codex image input is not an image-generation contract. The default remains
API mode for predictable throughput. Runner-first is useful during controlled testing because a heartbeat check gives
immediate API fallback when the workstation is offline; relying on the runner alone still requires concurrency,
capacity and account-limit measurements.

The Docker runtime excludes Node/Codex. The runner uses a separate random token, Redis TTLs and active-job checks. The
legacy `cli` configuration value is accepted as a compatibility alias for `runner`, but new deployments use `runner`.

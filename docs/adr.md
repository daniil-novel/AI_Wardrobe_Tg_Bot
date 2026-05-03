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

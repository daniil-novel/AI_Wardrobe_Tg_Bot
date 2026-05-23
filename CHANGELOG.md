# Changelog

## 0.2.0-rc.1 - 2026-05-21

- Hardened Telegram auth with persistent user upsert, refresh-token rotation, logout revocation and production startup secret validation.
- Replaced public sample responses in wardrobe, looks, outfits, wishlist, style, designer, marketplace and privacy flows with authenticated user-scoped database access or explicit disabled-provider errors.
- Reworked uploads and AI task orchestration to persist upload/image/task state, validate image payloads, enqueue Celery work and persist worker side effects for garment items, privacy receipts and AI request records.
- Added Mini App Telegram `initData` authentication, bearer-token API client, refresh retry and authenticated wardrobe/upload calls.
- Added production compose override, readiness/liveness/metrics endpoints, webhook-mode bot startup and release documentation for secrets, migrations, private backing services and readiness checks.
- Added production hardening and auth-boundary tests; switched local verification to Python 3.12 through `uv run --extra dev`.
- Removed remaining runtime demo fallbacks from the Mini App wardrobe/outfit screens; frontend state now comes from authenticated backend API calls.
- Replaced worker placeholder research/outfit tasks with OpenRouter-backed persistence into `garment_items`, `outfit_cards` and `ai_requests`.
- Added local MinIO bucket initialization and a non-root application container user for safer full-stack Docker runs.
- Switched backend Docker images to frozen `uv.lock` installs, removed bind-mounted backend runtime paths, added MinIO readiness gating and bounded worker concurrency.
- Added structured JSON logging with request ids, latency, status, hashed user identifiers and automatic redaction for tokens, keys, passwords and signed URLs.

## 0.1.0 - 2026-05-03

- Bootstrapped FastAPI, aiogram, Celery, SQLAlchemy, Alembic and React Mini App monorepo.
- Added v0.2.2 database model surface for users, uploads, wardrobe, looks, outfits, AI usage, style DNA, wishlist, privacy, marketplace, billing and notifications.
- Added all documented API endpoint groups from v0.2, v0.2.1 and v0.2.2.
- Added Docker Compose local stack with PostgreSQL, Redis, MinIO, API, bot, worker and Mini App.
- Added Ruff, Mypy, pre-commit, env template and deployment documentation.
- Added root API route, optional local env handling, port overrides, smoke tests and deployment contract tests.
- Wired Mini App controls, direct photo upload, upload status polling, retry/delete actions and Telegram bot photo registration through the backend upload API.

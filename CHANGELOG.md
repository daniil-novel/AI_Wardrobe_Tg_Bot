# Changelog

## 0.3.1 - 2026-07-06

Fix broken image uploads in production and make every Mini App control real.

- Fixed the production outage that broke uploads: the DB session dependency returned the session out of its generator, leaking one pooled connection per request until `QueuePool limit reached` took every endpoint down; sessions are now yielded and closed per request (regression test added).
- Fixed the Mini App auth race: screens checked the token once on mount before Telegram auth finished, so cold opens showed no weather, wardrobe or outfits until a tab switch.
- Designer chat persists proposed outfits (with item links, explanation and score) and drops hallucinated item ids; the day-scenario box, «Теплее», «Другой» and «Похожий» all go through it.
- «Выбрать» records select/wear history, hearts persist favorites, «Собрать с выбранными» builds an anchored outfit, favorites shows all outfits with a working «Избранные» tab.
- The hero outfit renders real item photos; rule-based outfits use Russian titles/explanations instead of echoing the prompt; `OutfitRead` exposes `item_ids`.
- Geolocation failures fall back to Moscow weather with a hint; preference chips wrap instead of clipping.
- Designer and outfit-recommendation POSTs are rate-limited in the `ai` bucket; image analysis upgraded to `google/gemini-2.5-pro`.
- Verified in a real Chromium run against production (initData passed through the official `tgWebAppData` fragment): auth, photo upload → AI card, wardrobe photos and Russian labels, designer tools/chat, favorites — 0 console errors, 0 failed requests.

## 0.3.0 - 2026-07-05

Production release: deployed to a VPS behind TLS and connected to Telegram (@wwardrobeai_bot).

- Fixed production webhook bot startup crash: replaced nested `web.run_app` with `AppRunner`/`TCPSite` and normalized the webhook URL join.
- Fixed first-time Telegram auth: new users are flushed before session insert, so `/auth/telegram` no longer fails with a NULL `user_id`.
- Implemented the Telegram photo pipeline end to end: `transfer_telegram_upload` downloads the Bot API file, validates magic bytes and size, stores the object in S3, chains AI analysis and classifies unrecoverable Telegram file errors without burning retries.
- Fixed transfer idempotency: queued uploads are no longer skipped as "already transferred".
- Workers now consume all routed Celery queues (`-Q celery,ai,research,recommendations,notifications`); previously AI tasks were routed to queues nobody consumed.
- AI analysis sends private images to OpenRouter as inline base64 data URLs; presigned links into the private MinIO network were unreachable for providers and leaked internal endpoints.
- Made garment analysis parsing resilient: explicit JSON schema in the system prompt, markdown fence trimming, scalar season/style coercion and percent-scale confidence normalization.
- Upload and AI retry endpoints now re-enqueue real Celery tasks instead of only rewriting statuses.
- `send_notification` actually delivers messages through the Bot API.
- Added Redis-backed fixed-window rate limiting for auth/upload/AI endpoint groups with fail-open behavior, per-user/IP scoping and `Retry-After` headers.
- Fixed production compose merge semantics with `!reset`/`!override`: database, broker and object-storage host ports are actually removed, the API/bot bind to loopback ports for the reverse proxy and the bot service no longer hides behind the `telegram` profile.
- Mini App shell now loads `telegram-web-app.js`, without which `initData` auth never started inside Telegram.
- Added shared image validation in `aiwardrobe_core.image_validation`, regression tests for the new pipeline, rate limiter, auth flush and LLM parsing (70 tests, coverage gate 67%).

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
- Added coverage-enabled regression tests for Telegram bot upload registration, worker fail-closed behavior, upload-store state transitions, LLM JSON validation and storage-key sanitization.
- Added Mermaid architecture and database schema documentation, including the Redis/RabbitMQ/Kafka production broker decision.
- Added RabbitMQ as the production Celery broker while keeping Redis for cache state, task results and operational counters.

## 0.1.0 - 2026-05-03

- Bootstrapped FastAPI, aiogram, Celery, SQLAlchemy, Alembic and React Mini App monorepo.
- Added v0.2.2 database model surface for users, uploads, wardrobe, looks, outfits, AI usage, style DNA, wishlist, privacy, marketplace, billing and notifications.
- Added all documented API endpoint groups from v0.2, v0.2.1 and v0.2.2.
- Added Docker Compose local stack with PostgreSQL, Redis, MinIO, API, bot, worker and Mini App.
- Added Ruff, Mypy, pre-commit, env template and deployment documentation.
- Added root API route, optional local env handling, port overrides, smoke tests and deployment contract tests.
- Wired Mini App controls, direct photo upload, upload status polling, retry/delete actions and Telegram bot photo registration through the backend upload API.

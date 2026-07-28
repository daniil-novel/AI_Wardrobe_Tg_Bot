# Changelog

## [Unreleased]

### Added

- Hybrid real-AI execution modes (`api`, `runner`, `hybrid`) with configurable API-first/runner-first fallback; `cli`
  remains a compatibility alias.
- Authenticated outbound-HTTPS local Codex runner with Redis TTL/heartbeat relay, image inputs, strict JSON Schema,
  saved-auth or opt-in Ollama/LM Studio, subprocess timeout/output limits and `/health/ai` diagnostics.
- Windows runner start/stop and real relay-canary scripts; server Docker images remain free of Codex credentials,
  binaries and Node.
- Actual provider/model provenance for AI reservations, completions and privacy receipts.
- User-controlled recognition editor with proposed region, touch/mouse selection, keyboard move/resize, whole-photo mode, undo/redo/reset, client-side crop and persisted selection provenance.
- Consent-safe avatar profiles, normalized measurements, asynchronous avatar generation and multi-item virtual try-on jobs.
- Avatar revocation lifecycle that clears consent/profile measurements and deletes derived avatar/try-on objects from S3 and PostgreSQL.
- Server-side effective entitlements from subscription or promo grants, plus `GET /billing/me` and `POST /billing/promos/redeem`.
- HMAC-hashed, expiring and redemption-limited promo codes with a secure one-day code creation tool.
- Transactional monthly quotas for image analysis, avatar generations and virtual try-ons; retries reuse analysis reservations and failed requests release quota slots.
- Separate `build:subscriptions` and `build:open` Mini App artifacts.
- Prometheus-compatible per-route HTTP counters, latency histograms and process uptime metrics.
- Commercial integrity migration with partial unique indexes, idempotency keys and check constraints.
- Market/pricing, UX, performance, database, security/privacy, engineering-loop and release-readiness reports.

### Changed

- OpenRouter API behavior remains unchanged and is still the pixel-generation boundary, while garment recognition,
  research, outfit generation and designer chat can run through the trusted local Codex runner.
- Codex prompts now travel over stdin and the child process receives a secret-minimized environment; user images are
  treated as untrusted data and exist only in an ephemeral working directory.
- Studio now shows stacked mobile tariff cards, explicit monthly generation limits, promo activation and honest payment-disabled states.
- Avatar prompts preserve visible identity and body proportions without slimming, beautification or sexualization.
- Bottom navigation uses compact visible labels with full accessible names; horizontal chips no longer expose system scrollbars at the tested mobile viewport.
- Telegram haptics are gated by supported WebApp versions.
- Preview Free plan limit now matches the server configuration.
- README now documents both variants, promo creation, quality checks and production gates.

### Fixed

- Commercial-integrity migration now repairs legacy duplicate analysis reservations by preserving every audit row and
  clearing only duplicate task links before creating the partial unique index.
- Runner shutdown now terminates the complete Python/Codex process tree; the first relay canary exposed an orphaned
  child process when `uv run` was used as the persisted PID.
- Direct uploads can no longer bypass the displayed monthly AI quota.
- Worker completion no longer creates a second billable analysis row.
- Queue/provider failures no longer consume a monthly quota slot.
- Removed a duplicate `original_image_id` assignment in the direct upload path.
- Interactive selection no longer uses an image-only ARIA role and can be adjusted from the keyboard.

### Security

- Plaintext promo codes are never stored in the database.
- Face/body consent revocation deletes sensitive derived images instead of only unlinking them.
- Billable-request and promo concurrency use database row locks.
- Metrics exclude user, garment, promo and storage identifiers.
- Runner endpoints are excluded from OpenAPI, use constant-time bearer verification, enforce minimum secret strength,
  bound payloads and reject responses for expired jobs.

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

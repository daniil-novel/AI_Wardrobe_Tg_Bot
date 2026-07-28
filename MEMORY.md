# Project memory

Последнее обновление: 2026-07-29.

## Product

AI Wardrobe — Telegram-first private wardrobe assistant: upload/crop garments, wardrobe-grounded outfits, AI designer, consent-safe avatar and virtual try-on.

Ключевая дифференциация: controllable selection на сложных фото, Telegram onboarding, privacy lifecycle и сохранение пропорций без beautification. Avatar сам по себе не уникален — Acloset/Pureple уже имеют try-on.

## Architecture

- FastAPI + SQLAlchemy/PostgreSQL;
- aiogram bot;
- Celery + RabbitMQ, Redis results/cache/rate limits;
- private S3/MinIO;
- React/TypeScript/Vite Telegram Mini App;
- provider-neutral `LlmGateway`: unchanged OpenRouter API and an outbound-HTTPS local Codex runner for analysis/text;
  OpenRouter for pixel generation.

## Durable decisions

- Не использовать mock как пользовательский AI result.
- `ENABLE_BILLING_PAYMENTS=false` до webhook, actual COGS and staging proof.
- Promo plaintext показывается один раз; DB хранит HMAC hash.
- Expensive requests резервируются transactionally and retry-idempotently.
- Failed requests release monthly quota.
- Avatar/try-on require explicit consent and derived assets are deleted on revoke.
- Original wardrobe upload не удаляется при avatar revoke, но reference link очищается.
- Full Go rewrite отклонён до measured CPU profile.
- Two frontend variants come from one codebase: `build:subscriptions`, `build:open`.
- `AI_EXECUTION_MODE=api|runner|hybrid` (`cli` is a compatibility alias); the local runner handles recognition/text,
  while product/avatar/try-on pixel generation remains API-only until a validated local image-generation adapter
  exists.
- Codex runs only on the trusted Windows workstation. The VPS stores bounded-TTL Redis jobs and exposes hidden
  bearer-authenticated long-poll endpoints; the workstation opens no inbound port and the VPS contains no Codex auth.
- `runner_first` requires a fresh heartbeat and falls back immediately to OpenRouter when the workstation is offline.
- Codex CLI subprocess receives prompts through stdin, runs in an ephemeral read-only directory and does not inherit
  OpenRouter, Telegram or JWT secrets.

## Current local evidence

- 129 tests passed after the relay implementation; coverage 69.19%;
- Ruff/Mypy/typecheck pass;
- subscription bundle 213.61 kB JS / 66.66 kB gzip;
- open bundle 209.63 kB JS / 65.67 kB gzip;
- TestClient public routes ≈190 RPS, p95 <8 ms;
- all six tabs visually inspected at 390×844;
- Claude Code Opus read-only review completed.
- PostgreSQL fresh up/down/up and committed-v0.3.1 → current migration upgrade passed;
- QA API with PostgreSQL + Redis returned readiness 200;
- one unused 24-hour Premium promo is stored in the isolated QA DB; plaintext exists only in the handoff.
- Codex CLI 0.144.1 real smoke passed for JSON, strict output schema, UTF-8 Russian text and `--image` input.
- three local end-to-end Codex JSON probes: median 6.165 s, min 6.051 s, max 7.656 s; no queue/image load.
- Real Redis + FastAPI + HTTPS-contract relay canary returned the requested JSON through Codex CLI in 28.2 s on the
  first run and 5.2 s on the repeated run. The repeated lifecycle check found zero leftover processes/listeners.

## Known blockers

- migration 0001 uses live metadata;
- no payment provider/webhook;
- existing v0.3.1 production is healthy over HTTPS and SSH access has recovered; the new release backup/deploy/rollback
  and post-deploy browser E2E are the current gate;
- no live consented avatar fidelity validation;
- no semantic segmentation/brush/zoom;
- no actual provider cost ingestion or end-to-end traces.
- per-request Codex process startup is intentionally a privacy/dev path and still needs concurrency/capacity
  benchmarking before runner-only production reliance.

## Safe commands

```powershell
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy packages/core apps/api apps/bot apps/worker
uv run --extra dev python -m pytest
npm --prefix apps/miniapp run typecheck
npm --prefix apps/miniapp run build:subscriptions
npm --prefix apps/miniapp run build:open
uv run --extra dev python scripts/benchmark-api.py
./scripts/codex-runner-canary.ps1
```

## Next production gate

Create a fresh production dump/source/static backup, deploy the subscription variant with hybrid runner-first fallback,
start the local runner against production, verify fallback and every Mini App tab in a real browser, then retain the
open variant as a separately versioned build artifact. Never commit promo plaintext or runner tokens.

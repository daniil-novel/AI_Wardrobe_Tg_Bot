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

## Current evidence

- 138 tests passed after production hardening; coverage 70.11%;
- Ruff/Mypy/typecheck pass;
- final subscription bundle 214.31 kB JS / 66.85 kB gzip;
- open bundle 209.63 kB JS / 65.67 kB gzip;
- TestClient public routes ≈190 RPS, p95 <8 ms;
- all six tabs, editor, promo, avatar and try-on visually inspected at 390×844 in production;
- final full E2E: upload ready, 18 items, avatar/try-on completed, zero console/network/layout issues;
- Claude Code Opus initial and post-deploy read-only reviews completed.
- PostgreSQL fresh up/down/up and committed-v0.3.1 → current migration upgrade passed;
- QA API with PostgreSQL + Redis returned readiness 200;
- one-day production promo flow was redeemed by the synthetic E2E user; a separate unused code is generated only at
  final handoff.
- Codex CLI 0.144.1 real smoke passed for JSON, strict output schema, UTF-8 Russian text and `--image` input.
- three local end-to-end Codex JSON probes: median 6.165 s, min 6.051 s, max 7.656 s; no queue/image load.
- Real Redis + FastAPI + HTTPS-contract relay canary returned the requested JSON through Codex CLI in 28.2 s on the
  first run and 5.2 s on the repeated run. The repeated lifecycle check found zero leftover processes/listeners.
- Production runner image recognition completed in about 57 s during the final run; full upload analysis including six
  API-generated product images completed in 104.3 s. A targeted try-on completed in 11.0 s without retry.
- Production is at migration `0005`; API/worker health, rotating files, stdout logs and hybrid runner heartbeat are live.

## Known blockers

- migration 0001 uses live metadata;
- no payment provider/webhook;
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

## Next commercial gate

Add payment webhooks/refunds, consented avatar-fidelity evidence, automated off-host backups and provider/queue SLO
dashboards. Keep promo plaintext, runner tokens and Telegram initData outside Git.

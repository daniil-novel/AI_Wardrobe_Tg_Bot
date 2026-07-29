# AI Wardrobe

Telegram-first AI digital wardrobe: FastAPI, aiogram, Celery and a React Telegram Mini App.

The app turns user-controlled photo regions into wardrobe cards, builds grounded outfits from real items, and includes a consent-safe avatar/virtual try-on preview. Subscription UX is feature-flagged; real payments remain disabled until provider, webhook and staging checks are complete.

## Current feature set

- Telegram initData auth, JWT access/refresh sessions and user isolation.
- Direct Mini App and Telegram photo upload to private S3-compatible storage.
- Pre-upload recognition editor:
  - proposed person region;
  - touch/mouse drag;
  - keyboard move/resize;
  - whole-photo mode;
  - undo/redo/reset;
  - client crop and server-side selection provenance.
- Switchable real-AI execution: unchanged OpenRouter API mode, an outbound-HTTPS local Codex runner, or an ordered
  hybrid fallback.
- Multi-item garment analysis with strict Pydantic/JSON Schema validation and background-clean product images.
- Wardrobe, looks, outfits, favorites, weather and wardrobe-grounded AI designer.
- Consent-safe avatar profile with normalized measurements and derived-data deletion.
- Asynchronous virtual try-on of selected wardrobe items.
- Free/Premium/Pro entitlements, monthly quotas and HMAC-hashed promo grants.
- Subscription-enabled and open/no-paywall frontend builds.
- JSON request logs, secret redaction, health/readiness and Prometheus-compatible API latency metrics.

Avatar and try-on outputs are visual simulations, not physical sizing guarantees. The application must not claim anthropometric or fit accuracy without a validated provider study.

## Requirements

- Python 3.12
- Node.js 22
- `uv`
- Docker Desktop with a working Linux engine for the full local stack
- real Telegram/OpenRouter secrets for provider and image-generation flows
- optional Codex CLI 0.144+ with saved authentication on the trusted workstation that runs the local runner

## Configuration

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Required for real integrations:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
OPENROUTER_API_KEY=
JWT_SECRET_KEY=
PROMO_HASH_SECRET=
MINIAPP_PUBLIC_URL=
```

Never commit `.env`, promo plaintext, Telegram initData or provider keys. Production startup rejects default JWT, database and S3 credentials.

AI analysis/text execution is selected independently from pixel generation:

```text
AI_EXECUTION_MODE=api          # unchanged OpenRouter path; default
AI_EXECUTION_MODE=runner       # local Codex runner for recognition/text
AI_EXECUTION_MODE=hybrid       # ordered runner/API fallback
AI_HYBRID_PREFERENCE=runner_first
CODEX_RUNNER_TOKEN=            # random shared secret, at least 32 characters
CODEX_RUNNER_WAIT_TIMEOUT_SECONDS=90
```

The workstation runner has its own ignored `.env.runner.local`:

```text
CODEX_RUNNER_SERVER_URL=https://your-domain.example/api
CODEX_RUNNER_TOKEN=            # exactly the same value as the server
CODEX_CLI_COMMAND=codex
CODEX_CLI_MODEL=
CODEX_CLI_LOCAL_PROVIDER=none  # or ollama/lmstudio for `codex exec --oss`
```

The local service long-polls authenticated internal endpoints over outbound HTTPS; the workstation exposes no inbound
port. Jobs and responses are held in Redis only for a bounded TTL. A fresh heartbeat is required before dispatch, so
`hybrid + runner_first` falls back immediately to the existing OpenRouter call when the workstation is offline.

`runner` does not silently emulate image generation. Product-card generation, avatar rendering and virtual try-on
still require `OPENROUTER_API_KEY`. In runner-only mode wardrobe analysis remains real, while generated image
derivatives degrade honestly to the existing normalized-original fallback or a provider-not-configured state.

The CLI runner uses an ephemeral temporary directory, `read-only` sandbox, stdin prompts, strict JSON Schema, timeout
and output limits. Application secrets are removed from the child environment. Set
`CODEX_CLI_ALLOW_API_KEY_ENV=true` only on a trusted workstation that must pass `CODEX_API_KEY`; saved Codex/ChatGPT
auth is preferred for local use. Prompts, private image bytes and raw CLI stderr are excluded from application logs.

If standard ports are occupied, use the host-port variables in `.env`:

```text
API_HOST_PORT=8010
MINIAPP_HOST_PORT=5174
POSTGRES_HOST_PORT=55432
REDIS_HOST_PORT=56379
MINIO_HOST_PORT=59000
MINIO_CONSOLE_HOST_PORT=59001
```

## Full local stack

```powershell
docker compose up --build
docker compose exec api alembic upgrade head
```

Open:

- API docs: `http://localhost:8000/docs`
- Mini App: `http://localhost:5173`
- MinIO console: `http://localhost:9001`

The bot is opt-in locally:

```powershell
docker compose --profile telegram up bot
```

Telegram WebView testing requires HTTPS. Configure a tunnel/domain and set `MINIAPP_PUBLIC_URL`.

The Docker image intentionally contains neither Codex nor workstation credentials. To start the runner after placing
the ignored environment file:

```powershell
./scripts/start-codex-runner.ps1
Invoke-RestMethod https://your-domain.example/api/health/ai
```

Stop it with `./scripts/stop-codex-runner.ps1`. The PID represents the actual Python launcher and shutdown recursively
terminates its Codex children. Validate a local relay before a deployment with
`./scripts/codex-runner-canary.ps1`; it creates an ephemeral token, runs a real `codex exec`, and verifies that no
runner/API process is left behind.

For the trusted Windows test workstation, install the idempotent per-user logon task:

```powershell
./scripts/install-codex-runner-task.ps1
```

The task launches the same ignored environment/configuration after logon and uses `MultipleInstances=IgnoreNew`.

## Frontend development and variants

```powershell
npm --prefix apps/miniapp install
npm --prefix apps/miniapp run dev
npm --prefix apps/miniapp run typecheck
```

Build with subscription UI:

```powershell
npm --prefix apps/miniapp run build:subscriptions
```

Output: `apps/miniapp/dist/subscription`.

Build without paywall/subscription UI:

```powershell
npm --prefix apps/miniapp run build:open
```

Output: `apps/miniapp/dist/open`.

These are frontend artifacts, not standalone production deployments: both still require the authenticated API, database, object storage and workers.

## Promo codes

Apply migrations first, then create a high-entropy one-day Premium grant:

```powershell
uv run python scripts/create-promo.py --hours 24 --max-redemptions 1 --valid-days 30
```

The command writes only the keyed hash to PostgreSQL and prints the plaintext once. Store it in a secure test channel; do not add it to a file or Git.

Redeem through:

```text
POST /billing/promos/redeem
Authorization: Bearer <access token>
{"code":"AW-1DAY-..."}
```

During the 2026-07-28 audit, a dedicated `aiwardrobe-qa` PostgreSQL container was migrated up/down/up on host port
`55433`, and one unused 24-hour Premium promo was inserted and read back. Its plaintext is intentionally not stored in
the repository; it is reported only in the audit handoff. The ignored `.env.qa` file contains the matching local
database URL and HMAC secret.

To target that database in the current PowerShell session:

```powershell
Get-Content .env.qa |
  Where-Object { $_ -and -not $_.StartsWith("#") } |
  ForEach-Object {
    $name, $value = $_.Split("=", 2)
    Set-Item -Path "Env:$name" -Value $value
  }
uv run uvicorn aiwardrobe_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

The QA container is deliberately separate from production and remains available as
`aiwardrobe-qa-postgres-1`. A Telegram-authenticated test user is created on first login.

## Quality checks

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

PowerShell smoke:

```powershell
./scripts/smoke-local.ps1 -ApiUrl http://localhost:8000 -MiniAppUrl http://localhost:5173
```

## Repository layout

```text
apps/api       FastAPI app, auth, routes, request metrics
apps/bot       aiogram Telegram bot
apps/worker    Celery AI/storage/notification tasks
apps/miniapp   React Telegram Mini App
packages/core  Settings, ORM, schemas, security, AI/storage/billing services
migrations     Alembic revisions
scripts        Promo creation, smoke and benchmark tools
tests          Unit/contract/integration-style regression tests
docs           Architecture, API, deploy and independent review notes
```

## Project evidence

- [Project audit](PROJECT_AUDIT.md)
- [Market and pricing](MARKET_AND_PRICING_RESEARCH.md)
- [UX screen audit](UX_SCREEN_AUDIT.md)
- [Performance baseline](PERFORMANCE_BASELINE.md)
- [Database review](DATABASE_REVIEW.md)
- [Security/privacy review](SECURITY_PRIVACY_REVIEW.md)
- [Engineering loop](ENGINEERING_LOOP_REPORT.md)
- [Release readiness](RELEASE_READINESS.md)
- [Production bug report](BUG_REPORT_2026-07-29.md)
- [Claude Code review](docs/reviews/CLAUDE_DESIGN_REVIEW.md)
- [Claude Code post-deploy review](docs/reviews/CLAUDE_POSTDEPLOY_REVIEW_2026-07-29.md)

## Production status

The 2026-07-29 subscription build is deployed at
`https://v353999.hosted-by-vdsina.com`, with `hybrid + runner_first`, live OpenRouter fallback and a connected local
Codex runner. Production is at migration `0005`; the final authenticated browser trace is clean and documented in the
bug report.

`ENABLE_BILLING_PAYMENTS=false` remains intentional. Public paid launch remains blocked until:

- payment invoices/webhooks/refunds are signed and idempotent;
- actual provider tokens/credits/cost are persisted;
- consented avatar-fidelity, load/soak and legal/privacy checks pass;
- automated off-host backup/restore, provider/queue dashboards and alerting are in place.

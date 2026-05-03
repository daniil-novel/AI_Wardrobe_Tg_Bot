# AI Wardrobe Telegram Bot + Mini App

Telegram-native AI digital wardrobe: FastAPI backend, aiogram bot, Celery workers and React Telegram Mini App.

## What Is Included

- Full v0.2.2 project scaffold based on the supplied TZ, UI/UX spec, design tokens and mobile prototype.
- FastAPI API with all documented endpoint groups.
- PostgreSQL schema through SQLAlchemy 2 and Alembic.
- Celery workers for image analysis, research, recommendations and notifications.
- aiogram v3 Telegram bot with `/start`, `/upload`, `/wardrobe`, `/favorites`, `/delete_me` and photo intake.
- React + TypeScript + Vite Mini App with mobile-first screens: Today, Wardrobe, Add, Designer, Favorites.
- Real-provider wiring only: OpenRouter and Telegram require real secrets in `.env`.

## Local Run

1. Create env:

```bash
cp .env.example .env
```

2. Fill required secrets:

```text
TELEGRAM_BOT_TOKEN=
OPENROUTER_API_KEY=
JWT_SECRET_KEY=
MINIAPP_PUBLIC_URL=
```

3. Start local stack:

```bash
docker compose up --build
```

4. Apply migrations:

```bash
docker compose exec api alembic upgrade head
```

5. Open:

- API: `http://localhost:8000/docs`
- Mini App dev server: `http://localhost:5173`
- MinIO Console: `http://localhost:9001`

Telegram Mini Apps require HTTPS for real WebView testing. Use a tunnel such as Cloudflare Tunnel or ngrok and set `MINIAPP_PUBLIC_URL` to that URL.

## Local Run Without Telegram Server

The API, frontend, PostgreSQL, Redis and MinIO can run locally without exposing a webhook. The bot still requires a real `TELEGRAM_BOT_TOKEN` because mock Telegram mode is intentionally disabled.

## Checks

```bash
ruff check .
ruff format --check .
mypy packages/core apps/api apps/bot apps/worker
pytest
npm --prefix apps/miniapp run build
```

## Repository Layout

```text
apps/api       FastAPI app and routers
apps/bot       aiogram Telegram bot
apps/worker    Celery workers
apps/miniapp   React Telegram Mini App
packages/core  Shared settings, DB, schemas, security, AI/storage/billing integrations
migrations     Alembic schema migrations
docs           Architecture, deploy, ADR, API notes, tech debt
```

## Security Notes

- Do not commit `.env`.
- OpenRouter and Telegram tokens are backend-only.
- Private images live in S3-compatible object storage, not PostgreSQL.
- Web research must use extracted clothing descriptions only, never private photos.
- Heavy AI work must run in workers, not API or bot event loops.

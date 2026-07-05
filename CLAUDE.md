# CLAUDE.md

## Язык и стиль работы

- Всегда отвечай пользователю на русском языке.
- Пиши коротко, по делу и с конкретными командами/файлами, когда это полезно.
- Перед изменениями в коде сначала посмотри существующую структуру проекта и текущие `.md`-файлы.
- Не придумывай поведение приложения: сверяйся с `README.md`, `docs/architecture.md`, `docs/api.md`, `docs/deploy.md`, `docs/production_blockers.md`, `docs/tech_debt.md` и `docs/adr.md`.
- Если нужны свежие сведения, внешние сервисы, браузерная проверка, GitHub, Telegram WebView или другая интеграция, используй доступные MCP-инструменты.
- Если задача связана с тестированием, Python, фронтендом, деплоем, GitHub, браузером или документацией, сначала проверь и применяй подходящие скиллы.

## Что это за проект

AI Wardrobe Telegram Bot + Mini App: Telegram-native цифровой гардероб с AI-анализом изображений.

Основные части:

- `apps/api` - FastAPI backend.
- `apps/bot` - aiogram v3 Telegram bot.
- `apps/worker` - Celery workers для AI, research, recommendations, notifications.
- `apps/miniapp` - React + TypeScript + Vite Telegram Mini App.
- `packages/core` - настройки, БД, схемы, security, storage, billing, LLM gateway.
- `migrations` - Alembic migrations.
- `tests` - pytest contract/regression/security/integration tests.
- `docs` - архитектура, API, деплой, ADR, production blockers, tech debt.

Стек:

- Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2.
- aiogram v3.
- Celery, Redis, RabbitMQ для production broker.
- PostgreSQL.
- S3-compatible storage, локально MinIO.
- OpenRouter для LLM.
- React 18, TypeScript, Vite, lucide-react.
- Docker Compose для локального и production-like запуска.

## Важные продуктовые границы

- Telegram handlers не должны содержать бизнес-логику гардероба: они делегируют в API/backend services.
- API schemas - это Pydantic DTO, отдельно от SQLAlchemy ORM models.
- Тяжёлая AI-работа должна выполняться в Celery workers, не в event loop API или bot.
- Приватные изображения хранятся в S3-compatible storage, не в PostgreSQL.
- Web research должен использовать только текстовые описания одежды, а не приватные фото, лица или оценку тела.
- OpenRouter и Telegram требуют реальные секреты; не включай mock-режимы там, где документация говорит, что они отключены.
- Billing и marketplace остаются за feature flags, пока нет production provider adapters.

## Локальный запуск

Создать `.env` при необходимости:

```bash
cp .env.example .env
```

Обязательные реальные секреты для полного сценария:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
OPENROUTER_API_KEY=
JWT_SECRET_KEY=
MINIAPP_PUBLIC_URL=
```

Запуск стека:

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

Адреса по умолчанию:

- API: `http://localhost:8000/docs`
- Mini App: `http://localhost:5173`
- MinIO Console: `http://localhost:9001`

Bot запускается отдельно, потому что ему нужен реальный Telegram token:

```bash
docker compose --profile telegram up bot
```

Если порты заняты, используй переменные из `.env.example`: `API_HOST_PORT`, `MINIAPP_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MINIO_HOST_PORT`, `MINIO_CONSOLE_HOST_PORT`.

## Проверки

Базовый набор перед сдачей изменений:

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy packages/core apps/api apps/bot apps/worker
uv run --extra dev python -m pytest
npm --prefix apps/miniapp run build
```

Локальный smoke test:

```powershell
./scripts/smoke-local.ps1 -ApiUrl http://localhost:8000 -MiniAppUrl http://localhost:5173
```

Frontend typecheck:

```bash
npm --prefix apps/miniapp run typecheck
```

## Тестирование Telegram и Mini App

- Для реальной Telegram Mini App проверки нужен HTTPS URL. Используй Cloudflare Tunnel, ngrok или другой tunnel и пропиши URL в `MINIAPP_PUBLIC_URL`.
- Проверяй сценарий в Telegram WebView, а не только в обычном браузере.
- Для браузерных и WebView-похожих проверок используй MCP/Browser/Playwright-инструменты, если они доступны.
- Проверяй основной e2e-путь: Telegram auth -> Mini App opens -> upload photo -> S3 object created -> Celery AI task -> item/look saved -> result visible in wardrobe.
- Отдельно проверяй Telegram photo flow: user sends photo -> bot registers upload -> backend stores state -> worker processes -> статус виден в Mini App.
- Не логируй и не вставляй в ответы реальные токены, `initData`, presigned URLs, Telegram file ids и приватные payload'ы.

## Production и безопасность

- Не коммить `.env`.
- Production startup должен блокироваться на default secrets и пустых обязательных secrets.
- В production наружу должен смотреть только TLS reverse proxy; PostgreSQL, Redis и object storage не открывать публично.
- Перед production нужны staging rollout, migrations-on-deploy, backup/restore drill, load/chaos/security checks, alerts и dashboards.
- Health endpoints: `/health/live`, `/health/ready`, `/metrics`.
- User-scoped API обязательно должен фильтровать данные по `user_id`.
- Privacy deletion должен удалять DB rows и S3 objects и оставлять audit/receipt там, где это предусмотрено архитектурой.

## Как вносить изменения

- Сохраняй существующие паттерны проекта.
- Для Python держи strict typing, Pydantic DTO и SQLAlchemy async boundaries.
- Для frontend соблюдай Telegram mobile-first UI, существующие design tokens/spec и не ломай WebView-эргономику.
- Для AI/worker изменений добавляй идемпотентность, статусы задач, классификацию ошибок и тесты.
- Для upload изменений проверяй content type, magic bytes, max size, S3 lifecycle и retry/delete behavior.
- Для auth/security изменений добавляй тесты на invalid/expired/revoked tokens, Telegram `initData` validation и user isolation.

## Документация-источник

При сомнениях ориентируйся на эти файлы:

- `README.md` - запуск, команды, layout, security notes.
- `docs/architecture.md` - контейнеры, доменные границы, AI pipeline, схема БД.
- `docs/api.md` - группы endpoint'ов.
- `docs/deploy.md` - deployment и Telegram WebView.
- `docs/production_blockers.md` - release checklist и production risks.
- `docs/tech_debt.md` - известный технический долг.
- `docs/adr.md` - архитектурные решения.

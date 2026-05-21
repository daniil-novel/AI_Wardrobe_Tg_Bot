# Deployment

## VPS With Docker Compose

1. Provision VPS with Docker and Docker Compose.
2. Create production `.env` from `.env.example`.
3. Point DNS to the VPS.
4. Put a TLS reverse proxy in front of `api:8000` and `miniapp:5173` or serve the Mini App build statically.
5. Run production compose with explicit secrets. The production override removes bind mounts, disables API reload,
   blocks default secrets through Compose interpolation and uses readiness checks:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec api alembic upgrade head
```

6. Configure Telegram bot menu and Mini App URL to the HTTPS domain.
7. Confirm `GET /health/live`, `GET /health/ready` and `GET /metrics` from inside the private network.
8. Keep PostgreSQL, Redis and MinIO off public host ports; expose only the TLS reverse proxy.
9. Configure backups for PostgreSQL and object storage, then run a restore drill before release.

Production startup is blocked when `JWT_SECRET_KEY`, PostgreSQL password or S3 credentials still use repository
defaults, or when Telegram/OpenRouter runtime secrets are empty.

The default compose file supports host port overrides through environment variables. On shared servers, set `API_HOST_PORT`, `MINIAPP_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MINIO_HOST_PORT` and `MINIO_CONSOLE_HOST_PORT` explicitly.

## Railway, Render Or Similar

- API service: Dockerfile command `uvicorn aiwardrobe_api.main:create_app --factory`.
- Worker service: `celery -A aiwardrobe_worker.celery_app:celery_app worker --loglevel=INFO`.
- Bot service: `python -m aiwardrobe_bot.main`.
- Frontend: build `apps/miniapp` and deploy static `dist`.
- Use managed PostgreSQL, Redis and S3-compatible storage.
- Run migrations as an explicit release step before routing production traffic to new API containers.
- Use webhook mode for the bot in production; polling is available only when `ENABLE_POLLING_BOT=true`.

## Local Telegram WebView

Telegram requires HTTPS Mini App URLs. For local development, expose `http://localhost:5173` through Cloudflare Tunnel or ngrok and set `MINIAPP_PUBLIC_URL`.

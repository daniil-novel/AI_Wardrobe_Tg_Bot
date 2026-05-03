# Deployment

## VPS With Docker Compose

1. Provision VPS with Docker and Docker Compose.
2. Create production `.env` from `.env.example`.
3. Point DNS to the VPS.
4. Put a TLS reverse proxy in front of `api:8000` and `miniapp:5173` or serve the Mini App build statically.
5. Run:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

6. Configure Telegram bot menu and Mini App URL to the HTTPS domain.
7. Switch bot from polling to webhook mode before high traffic.
8. Configure backups for PostgreSQL and object storage.

The default compose file supports host port overrides through environment variables. On shared servers, set `API_HOST_PORT`, `MINIAPP_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MINIO_HOST_PORT` and `MINIO_CONSOLE_HOST_PORT` explicitly.

## Railway, Render Or Similar

- API service: Dockerfile command `uvicorn aiwardrobe_api.main:create_app --factory`.
- Worker service: `celery -A aiwardrobe_worker.celery_app:celery_app worker --loglevel=INFO`.
- Bot service: `python -m aiwardrobe_bot.main`.
- Frontend: build `apps/miniapp` and deploy static `dist`.
- Use managed PostgreSQL, Redis and S3-compatible storage.

## Local Telegram WebView

Telegram requires HTTPS Mini App URLs. For local development, expose `http://localhost:5173` through Cloudflare Tunnel or ngrok and set `MINIAPP_PUBLIC_URL`.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY apps ./apps
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --upgrade pip && pip install ".[dev]"

ENV PYTHONPATH=/app/packages/core:/app/apps/api:/app/apps/bot:/app/apps/worker

CMD ["uvicorn", "aiwardrobe_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

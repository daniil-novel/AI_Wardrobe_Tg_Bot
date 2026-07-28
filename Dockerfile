FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY uv.lock ./
COPY apps ./apps
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --upgrade pip uv && uv sync --frozen --no-dev --no-editable

ENV PYTHONPATH=/app/packages/core:/app/apps/api:/app/apps/bot:/app/apps/worker
ENV PATH="/app/.venv/bin:${PATH}"

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["/app/.venv/bin/uvicorn", "aiwardrobe_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

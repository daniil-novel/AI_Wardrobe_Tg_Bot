from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.schemas import HealthResponse
from fastapi import APIRouter, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        missing_runtime_secrets=settings.missing_runtime_secrets,
    )


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    settings = get_settings()
    failures: list[str] = []
    try:
        async with get_session_factory()() as session:
            await session.execute(text("select 1"))
    except Exception:
        failures.append("database")
    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
    except Exception:
        failures.append("redis")
    if failures:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "failed": failures},
        )
    return {"status": "ready"}


@router.get("/metrics")
async def metrics() -> Response:
    settings = get_settings()
    body = "\n".join(
        [
            "# HELP aiwardrobe_app_info Application info.",
            "# TYPE aiwardrobe_app_info gauge",
            f'aiwardrobe_app_info{{env="{settings.app_env}"}} 1',
            "# HELP aiwardrobe_missing_runtime_secrets Missing runtime secrets.",
            "# TYPE aiwardrobe_missing_runtime_secrets gauge",
            f"aiwardrobe_missing_runtime_secrets {len(settings.missing_runtime_secrets)}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")

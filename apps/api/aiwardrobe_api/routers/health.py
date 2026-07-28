from aiwardrobe_core.codex_relay import CodexRelay
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.db import get_session_factory
from aiwardrobe_core.schemas import HealthResponse
from fastapi import APIRouter, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from aiwardrobe_api.metrics import render_prometheus_metrics

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        missing_runtime_secrets=settings.missing_runtime_secrets,
        ai_execution_mode=settings.ai_execution_mode,
        ai_analysis_provider=settings.ai_analysis_provider,
        image_generation_provider=settings.image_generation_provider,
    )


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ai")
async def ai_health() -> dict[str, str | bool]:
    settings = get_settings()
    runner_requested = settings.ai_execution_mode in {"runner", "cli", "hybrid"}
    runner_connected = await CodexRelay(settings).runner_is_connected() if runner_requested else False
    api_available = settings.ai_execution_mode in {"api", "hybrid"} and bool(settings.openrouter_api_key)
    return {
        "status": "ready" if api_available or runner_connected else "degraded",
        "execution_mode": settings.ai_execution_mode,
        "analysis_provider": settings.ai_analysis_provider,
        "image_generation_provider": settings.image_generation_provider,
        "openrouter_configured": bool(settings.openrouter_api_key),
        "codex_runner_requested": runner_requested,
        "codex_runner_connected": runner_connected,
    }


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
    body = render_prometheus_metrics(
        settings.app_env,
        len(settings.missing_runtime_secrets),
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")

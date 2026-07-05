from typing import Any
from uuid import UUID

import structlog
from aiwardrobe_core.config import get_settings
from aiwardrobe_core.weather import WeatherSummary, fetch_weather
from fastapi import APIRouter, HTTPException, Query, status

from aiwardrobe_api.dependencies import CurrentUser

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/weather", tags=["weather"])

CACHE_TTL_SECONDS = 1800

_redis_client: Any = None


def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        from redis.asyncio import Redis

        _redis_client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)
    return _redis_client


@router.get("", response_model=WeatherSummary)
async def weather_today(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    user_id: UUID = CurrentUser,
) -> WeatherSummary:
    _ = user_id
    cache_key = f"weather:{round(latitude, 2)}:{round(longitude, 2)}"
    try:
        cached = await _get_redis().get(cache_key)
        if cached:
            return WeatherSummary.model_validate_json(cached)
    except Exception as exc:
        logger.warning("weather.cache_unavailable", error=exc.__class__.__name__)

    try:
        summary = await fetch_weather(latitude, longitude)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Weather provider is unavailable.") from exc

    try:
        await _get_redis().set(cache_key, summary.model_dump_json(), ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("weather.cache_write_failed", error=exc.__class__.__name__)
    return summary

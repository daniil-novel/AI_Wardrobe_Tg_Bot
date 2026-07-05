import time
from typing import Any

import structlog
from aiwardrobe_core.config import Settings, get_settings
from aiwardrobe_core.logging import hash_identifier
from aiwardrobe_core.security import decode_access_token
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed fixed-window rate limiting for expensive endpoint groups.

    Fails open when Redis is unavailable: availability of the API is preferred over
    strict enforcement, and the failure is logged for operators.
    """

    def __init__(self, app: Any, settings: Settings | None = None, redis_client: Any = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()
        self._redis = redis_client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit_name_and_value = self._policy_for(request)
        if limit_name_and_value is None or not self.settings.rate_limit_enabled:
            return await call_next(request)
        policy, limit = limit_name_and_value

        window = int(time.time() // WINDOW_SECONDS)
        redis_key = f"ratelimit:{policy}:{self._client_key(request)}:{window}"
        try:
            count = await self._increment(redis_key)
        except Exception as exc:
            logger.warning("rate_limit.redis_unavailable", error=exc.__class__.__name__, policy=policy)
            return await call_next(request)

        if count > limit:
            retry_after = WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS
            return JSONResponse(
                {"detail": "Too many requests."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

    async def _increment(self, redis_key: str) -> int:
        client = self._get_redis()
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, WINDOW_SECONDS * 2)
        results = await pipe.execute()
        return int(results[0])

    def _get_redis(self) -> Any:
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        return self._redis

    def _policy_for(self, request: Request) -> tuple[str, int] | None:
        path = request.url.path
        if path.startswith("/auth"):
            return "auth", self.settings.rate_limit_auth_per_minute
        if path.startswith("/uploads") and request.method != "GET":
            return "uploads", self.settings.rate_limit_uploads_per_minute
        if path.startswith(("/ai", "/designer", "/outfits/recommend", "/outfits/from-prompt")) and (
            request.method != "GET"
        ):
            return "ai", self.settings.rate_limit_ai_per_minute
        return None

    @staticmethod
    def _client_key(request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            try:
                user_id = decode_access_token(authorization.removeprefix("Bearer ").strip())
                return f"user:{hash_identifier(str(user_id))}"
            except Exception:  # noqa: S110 - invalid token falls back to IP scoping
                pass
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

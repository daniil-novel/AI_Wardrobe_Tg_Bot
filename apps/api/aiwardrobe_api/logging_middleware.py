import time
from uuid import uuid4

import structlog
from aiwardrobe_core.logging import hash_identifier
from aiwardrobe_core.security import decode_access_token
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        start = time.perf_counter()
        user_hash = self._user_hash(request)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "http.request.failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                user_hash=user_hash,
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request.completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_hash=user_hash,
        )
        return response

    @staticmethod
    def _user_hash(request: Request) -> str | None:
        authorization = request.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return None
        try:
            user_id = decode_access_token(authorization.removeprefix("Bearer ").strip())
        except Exception:
            return None
        return hash_identifier(str(user_id))

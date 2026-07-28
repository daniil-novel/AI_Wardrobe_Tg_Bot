import json
import time
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

from aiwardrobe_core.config import Settings

_PREFIX = "aiwardrobe:codex-runner:v1"
_QUEUE_KEY = f"{_PREFIX}:queue"
_HEARTBEAT_KEY = f"{_PREFIX}:heartbeat"


class CodexRunnerError(RuntimeError):
    """Base error for the remote local-Codex relay."""


class CodexRunnerUnavailable(CodexRunnerError):
    """Raised when no local Codex runner has a fresh heartbeat."""


class CodexRelayJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    operation: Literal["analyze_image", "analyze_image_items", "generate_text_json"]
    prompt: str = Field(min_length=1, max_length=200_000)
    response_schema: Literal["GarmentAnalysis", "LookAnalysis", "json_object"]
    image_data_urls: list[str] = Field(default_factory=list, max_length=6)
    created_at_unix: float


class CodexRelayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "failed"]
    result: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=128)


class CodexRelay:
    """Redis relay shared by server workers and the authenticated HTTPS runner API."""

    def __init__(self, settings: Settings, redis_client: Any | None = None) -> None:
        self.settings = settings
        self._redis = redis_client
        self._owns_redis = redis_client is None

    async def runner_is_connected(self) -> bool:
        client = self._client()
        try:
            return bool(await client.exists(_HEARTBEAT_KEY))
        except RedisError:
            return False
        finally:
            await self._close_owned(client)

    async def heartbeat(self) -> None:
        client = self._client()
        try:
            await client.set(_HEARTBEAT_KEY, "1", ex=self.settings.codex_runner_heartbeat_ttl_seconds)
        finally:
            await self._close_owned(client)

    async def submit_and_wait(
        self,
        *,
        operation: Literal["analyze_image", "analyze_image_items", "generate_text_json"],
        prompt: str,
        response_schema: Literal["GarmentAnalysis", "LookAnalysis", "json_object"],
        image_data_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        job_id = uuid4()
        job_key = self._job_key(job_id)
        response_key = self._response_key(job_id)
        try:
            if not await client.exists(_HEARTBEAT_KEY):
                raise CodexRunnerUnavailable("No local Codex runner heartbeat is available.")
            job = CodexRelayJob(
                job_id=job_id,
                operation=operation,
                prompt=prompt,
                response_schema=response_schema,
                image_data_urls=image_data_urls or [],
                created_at_unix=time.time(),
            )
            encoded = job.model_dump_json().encode("utf-8")
            if len(encoded) > self.settings.codex_runner_max_payload_bytes:
                raise CodexRunnerError("Codex runner job exceeds the configured relay payload limit.")
            pipe = client.pipeline()
            pipe.set(job_key, encoded, ex=self.settings.codex_runner_job_ttl_seconds)
            pipe.rpush(_QUEUE_KEY, job_id.hex)
            await pipe.execute()
            response_item = await client.blpop(
                response_key,
                timeout=self.settings.codex_runner_wait_timeout_seconds,
            )
            if response_item is None:
                raise CodexRunnerUnavailable("Local Codex runner did not complete the job before its timeout.")
            raw_response = response_item[1]
            if isinstance(raw_response, bytes):
                raw_response = raw_response.decode("utf-8")
            response = CodexRelayResponse.model_validate_json(raw_response)
            if response.status == "failed":
                raise CodexRunnerError(f"Local Codex runner failed with {response.error_code or 'unknown_error'}.")
            if response.result is None:
                raise CodexRunnerError("Local Codex runner returned no result.")
            return response.result
        except RedisError as exc:
            raise CodexRunnerUnavailable("Codex runner relay is unavailable.") from exc
        finally:
            try:
                await client.delete(job_key, response_key)
            except RedisError:
                pass
            finally:
                await self._close_owned(client)

    async def claim(self) -> CodexRelayJob | None:
        client = self._client()
        try:
            await client.set(_HEARTBEAT_KEY, "1", ex=self.settings.codex_runner_heartbeat_ttl_seconds)
            deadline = time.monotonic() + self.settings.codex_runner_claim_timeout_seconds
            while True:
                remaining = max(1, int(deadline - time.monotonic()))
                item = await client.blpop(_QUEUE_KEY, timeout=remaining)
                if item is None:
                    return None
                raw_job_id = item[1]
                job_id = raw_job_id.decode("ascii") if isinstance(raw_job_id, bytes) else str(raw_job_id)
                raw_job = await client.get(self._job_key(UUID(hex=job_id)))
                if raw_job is not None:
                    return CodexRelayJob.model_validate_json(raw_job)
                if time.monotonic() >= deadline:
                    return None
        finally:
            await self._close_owned(client)

    async def complete(self, job_id: UUID, result: dict[str, Any]) -> bool:
        return await self._respond(
            job_id,
            CodexRelayResponse(status="completed", result=result),
        )

    async def fail(self, job_id: UUID, error_code: str) -> bool:
        return await self._respond(
            job_id,
            CodexRelayResponse(status="failed", error_code=error_code[:128]),
        )

    async def _respond(self, job_id: UUID, response: CodexRelayResponse) -> bool:
        client = self._client()
        job_key = self._job_key(job_id)
        response_key = self._response_key(job_id)
        try:
            if not await client.exists(job_key):
                return False
            encoded = response.model_dump_json().encode("utf-8")
            if len(encoded) > self.settings.codex_cli_max_output_bytes:
                raise CodexRunnerError("Codex runner response exceeds the configured output limit.")
            pipe = client.pipeline()
            pipe.rpush(response_key, encoded)
            pipe.expire(response_key, self.settings.codex_runner_job_ttl_seconds)
            pipe.delete(job_key)
            await pipe.execute()
            return True
        finally:
            await self._close_owned(client)

    def _client(self) -> Any:
        if self._redis is not None:
            return self._redis
        return Redis.from_url(
            self.settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=max(
                self.settings.codex_runner_claim_timeout_seconds,
                self.settings.codex_runner_wait_timeout_seconds,
            )
            + 5,
            decode_responses=False,
        )

    async def _close_owned(self, client: Any) -> None:
        if self._owns_redis:
            await client.aclose()

    @staticmethod
    def _job_key(job_id: UUID) -> str:
        return f"{_PREFIX}:job:{job_id.hex}"

    @staticmethod
    def _response_key(job_id: UUID) -> str:
        return f"{_PREFIX}:response:{job_id.hex}"


def relay_payload_size(payload: dict[str, Any]) -> int:
    """Return compact serialized size for endpoint pre-validation and tests."""
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

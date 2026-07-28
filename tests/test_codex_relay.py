import json
from collections import defaultdict
from typing import Any
from uuid import UUID, uuid4

import pytest
from aiwardrobe_api.routers.codex_runner import require_runner_token
from aiwardrobe_core.codex_relay import (
    CodexRelay,
    CodexRelayJob,
    CodexRunnerUnavailable,
)
from aiwardrobe_core.config import Settings
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.operations: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def set(self, *args: Any, **kwargs: Any) -> "FakePipeline":
        self.operations.append(("set", args, kwargs))
        return self

    def rpush(self, *args: Any, **kwargs: Any) -> "FakePipeline":
        self.operations.append(("rpush", args, kwargs))
        return self

    def expire(self, *args: Any, **kwargs: Any) -> "FakePipeline":
        self.operations.append(("expire", args, kwargs))
        return self

    def delete(self, *args: Any, **kwargs: Any) -> "FakePipeline":
        self.operations.append(("delete", args, kwargs))
        return self

    async def execute(self) -> None:
        for name, args, kwargs in self.operations:
            await getattr(self.redis, name)(*args, **kwargs)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.queues: dict[str, list[Any]] = defaultdict(list)
        self.response_result: dict[str, Any] | None = None

    async def exists(self, key: str) -> int:
        return int(key in self.values)

    async def set(self, key: str, value: Any, **_: Any) -> None:
        self.values[key] = value

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)
            self.queues.pop(key, None)

    async def rpush(self, key: str, value: Any) -> None:
        self.queues[key].append(value)

    async def expire(self, _key: str, _seconds: int) -> None:
        return None

    async def blpop(self, key: str, **_: Any) -> tuple[str, Any] | None:
        if self.queues[key]:
            return key, self.queues[key].pop(0)
        if self.response_result is not None and ":response:" in key:
            response = json.dumps({"status": "completed", "result": self.response_result})
            return key, response
        return None

    async def aclose(self) -> None:
        return None

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)


class BrokenRedis(FakeRedis):
    async def exists(self, key: str) -> int:
        raise RedisConnectionError(f"Unavailable key: {key}")


def runner_settings(**overrides: Any) -> Settings:
    return Settings.model_validate(
        {
            "ai_execution_mode": "runner",
            "codex_runner_token": "r" * 48,
            **overrides,
        }
    )


async def test_relay_fails_fast_when_runner_has_no_heartbeat() -> None:
    relay = CodexRelay(runner_settings(), FakeRedis())

    with pytest.raises(CodexRunnerUnavailable, match="heartbeat"):
        await relay.submit_and_wait(
            operation="generate_text_json",
            prompt="Return JSON.",
            response_schema="json_object",
        )


async def test_relay_wraps_redis_outage_for_hybrid_fallback() -> None:
    relay = CodexRelay(runner_settings(), BrokenRedis())

    with pytest.raises(CodexRunnerUnavailable, match="relay is unavailable"):
        await relay.submit_and_wait(
            operation="generate_text_json",
            prompt="Return JSON.",
            response_schema="json_object",
        )


async def test_relay_submits_job_and_returns_runner_result() -> None:
    fake = FakeRedis()
    await fake.set("aiwardrobe:codex-runner:v1:heartbeat", "1")
    fake.response_result = {"ok": True}
    relay = CodexRelay(runner_settings(), fake)

    result = await relay.submit_and_wait(
        operation="generate_text_json",
        prompt="Return JSON.",
        response_schema="json_object",
    )

    assert result == {"ok": True}
    assert len(fake.queues["aiwardrobe:codex-runner:v1:queue"]) == 1


async def test_relay_claims_and_completes_active_job() -> None:
    fake = FakeRedis()
    relay = CodexRelay(runner_settings(), fake)
    job_id = uuid4()
    job = CodexRelayJob(
        job_id=job_id,
        operation="analyze_image",
        prompt="Describe the garment.",
        response_schema="GarmentAnalysis",
        image_data_urls=["data:image/png;base64,AA=="],
        created_at_unix=1.0,
    )
    job_key = relay._job_key(job_id)
    await fake.set(job_key, job.model_dump_json().encode())
    await fake.rpush("aiwardrobe:codex-runner:v1:queue", job_id.hex)

    claimed = await relay.claim()
    accepted = await relay.complete(job_id, {"category": "top"})

    assert claimed == job
    assert accepted is True
    response_key = relay._response_key(job_id)
    response = json.loads(fake.queues[response_key][0])
    assert response == {
        "status": "completed",
        "result": {"category": "top"},
        "error_code": None,
    }


def test_runner_token_requires_exact_strong_bearer_value() -> None:
    settings = runner_settings()

    assert require_runner_token(f"Bearer {settings.codex_runner_token}", settings) is settings
    with pytest.raises(HTTPException) as exc_info:
        require_runner_token("Bearer wrong", settings)

    assert exc_info.value.status_code == 401


async def test_relay_rejects_completion_for_expired_job() -> None:
    relay = CodexRelay(runner_settings(), FakeRedis())

    assert await relay.complete(UUID(int=0), {"ok": True}) is False

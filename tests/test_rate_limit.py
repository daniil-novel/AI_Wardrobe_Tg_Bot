from typing import Any

from aiwardrobe_api.rate_limit import RateLimitMiddleware
from aiwardrobe_core.config import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakePipeline:
    def __init__(self, store: dict[str, int], fail: bool) -> None:
        self.store = store
        self.fail = fail
        self.key: str | None = None

    def incr(self, key: str) -> None:
        self.key = key

    def expire(self, key: str, ttl: int) -> None:
        pass

    async def execute(self) -> list[int]:
        if self.fail:
            raise ConnectionError("redis down")
        assert self.key is not None
        self.store[self.key] = self.store.get(self.key, 0) + 1
        return [self.store[self.key], 1]


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.store: dict[str, int] = {}
        self.fail = fail

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self.store, self.fail)


def build_app(redis_client: Any, **settings_overrides: Any) -> TestClient:
    settings_overrides.setdefault("rate_limit_enabled", True)
    settings_overrides.setdefault("rate_limit_auth_per_minute", 3)
    settings = Settings(**settings_overrides)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings, redis_client=redis_client)

    @app.post("/auth/telegram")
    async def auth_stub() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/items")
    async def items_stub() -> list[str]:
        return []

    return TestClient(app)


def test_rate_limit_returns_429_over_limit() -> None:
    client = build_app(FakeRedis())

    statuses = [client.post("/auth/telegram").status_code for _ in range(5)]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_rate_limit_429_includes_retry_after() -> None:
    client = build_app(FakeRedis())
    for _ in range(3):
        client.post("/auth/telegram")

    response = client.post("/auth/telegram")

    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 60


def test_rate_limit_fails_open_when_redis_is_unavailable() -> None:
    client = build_app(FakeRedis(fail=True))

    statuses = [client.post("/auth/telegram").status_code for _ in range(5)]

    assert statuses == [200] * 5


def test_rate_limit_skips_unmatched_paths() -> None:
    redis = FakeRedis()
    client = build_app(redis)

    for _ in range(10):
        assert client.get("/items").status_code == 200

    assert redis.store == {}


def test_rate_limit_disabled_by_setting() -> None:
    client = build_app(FakeRedis(), rate_limit_enabled=False)

    statuses = [client.post("/auth/telegram").status_code for _ in range(5)]

    assert statuses == [200] * 5


def test_rate_limit_scopes_clients_separately() -> None:
    redis = FakeRedis()
    client = build_app(redis)

    client.post("/auth/telegram", headers={"X-Forwarded-For": "10.0.0.1"})
    client.post("/auth/telegram", headers={"X-Forwarded-For": "10.0.0.2"})

    assert len(redis.store) == 2

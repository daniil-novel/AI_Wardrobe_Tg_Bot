from typing import Any
from uuid import uuid4

from aiwardrobe_core.auth_service import upsert_telegram_user


class FakeResult:
    def scalar_one_or_none(self) -> None:
        return None


class FakeSession:
    """New users must be flushed so user.id exists before the session row insert."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = False

    async def execute(self, _query: Any) -> FakeResult:
        return FakeResult()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()


async def test_upsert_new_telegram_user_flushes_id() -> None:
    session = FakeSession()

    user = await upsert_telegram_user(session, {"id": 777000777, "username": "e2e", "first_name": "E"})  # type: ignore[arg-type]

    assert session.flushed
    assert user.id is not None

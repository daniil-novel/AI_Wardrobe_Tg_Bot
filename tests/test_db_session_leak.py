import inspect
from pathlib import Path

from aiwardrobe_api import dependencies


def test_db_session_dependency_is_a_yield_generator() -> None:
    """A returning dependency leaks one pooled connection per request until GC.

    Production hit `QueuePool limit of size 5 overflow 10 reached` because the
    session was returned out of the generator instead of yielded through it.
    """
    assert inspect.isasyncgenfunction(dependencies.get_db_session)

    source = Path("apps/api/aiwardrobe_api/dependencies.py").read_text(encoding="utf-8")
    assert "yield session" in source
    assert "return session" not in source

from typing import Any
from uuid import uuid4

import pytest
from aiwardrobe_api.routers import designer
from aiwardrobe_core.models import GarmentItem
from aiwardrobe_core.schemas import DesignerChatRequest


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def __iter__(self) -> Any:
        return iter(self._items)


class FakeResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._items)


class FakeSession:
    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, _query: Any) -> FakeResult:
        return FakeResult(self.items)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self) -> None:
        self.commits += 1


def make_item(user_id: Any) -> GarmentItem:
    return GarmentItem(
        id=uuid4(),
        user_id=user_id,
        title="Синяя футболка",
        category="top",
        season=["summer"],
        main_color="синий",
        designer_attributes={},
    )


class FakeGateway:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def __call__(self, _settings: Any) -> "FakeGateway":
        return self

    async def generate_text_json(self, prompt: str, schema_name: str) -> dict[str, Any]:
        return self.response


async def test_designer_chat_persists_proposed_outfit(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    item = make_item(user_id)
    session = FakeSession([item])
    monkeypatch.setattr(
        designer,
        "LlmGateway",
        FakeGateway(
            {
                "reply": "Собрала тёплый образ.",
                "outfit": {
                    "title": "Тёплый городской",
                    "explanation": "База под погоду.",
                    "score": 88,
                    "comfort_score": 90,
                    "item_ids": [str(item.id)],
                },
            }
        ),
    )

    response = await designer.designer_chat(
        DesignerChatRequest(message="Что надеть завтра? Я мерзну."),
        user_id=user_id,
        session=session,  # type: ignore[arg-type]
    )

    assert response.reply == "Собрала тёплый образ."
    assert response.outfit_id is not None
    assert response.outfit_title == "Тёплый городской"
    assert response.outfit_item_ids == [item.id]
    assert response.outfit_score == 88.0
    assert session.commits == 1


async def test_designer_chat_without_outfit_returns_reply_only(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    session = FakeSession([make_item(user_id)])
    monkeypatch.setattr(
        designer,
        "LlmGateway",
        FakeGateway({"reply": "Уточните сценарий дня.", "outfit": None}),
    )

    response = await designer.designer_chat(
        DesignerChatRequest(message="Привет"),
        user_id=user_id,
        session=session,  # type: ignore[arg-type]
    )

    assert response.outfit_id is None
    assert response.reply == "Уточните сценарий дня."
    assert session.commits == 0


async def test_designer_chat_ignores_hallucinated_item_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    session = FakeSession([make_item(user_id)])
    monkeypatch.setattr(
        designer,
        "LlmGateway",
        FakeGateway(
            {
                "reply": "Образ готов.",
                "outfit": {"title": "X", "explanation": "", "score": 70, "item_ids": [str(uuid4()), "not-a-uuid"]},
            }
        ),
    )

    response = await designer.designer_chat(
        DesignerChatRequest(message="Собери образ"),
        user_id=user_id,
        session=session,  # type: ignore[arg-type]
    )

    assert response.outfit_id is None
    assert response.outfit_item_ids == []

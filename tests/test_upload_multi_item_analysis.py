from typing import Any
from uuid import uuid4

import pytest
from aiwardrobe_core.config import Settings
from aiwardrobe_core.enums import ProcessingStatus, UploadSource
from aiwardrobe_core.llm_gateway import GarmentAnalysis, LlmGatewayError, LookAnalysis
from aiwardrobe_core.models import GarmentItem, ImageAsset, LookCard, LookItem, Upload, User
from aiwardrobe_worker.tasks import analyze_upload, find_possible_duplicate

SETTINGS = Settings(openrouter_api_key="sk-test", telegram_bot_token="123:abc")


def make_garment(title: str, category: str = "top", color: str = "синий") -> GarmentAnalysis:
    return GarmentAnalysis(
        image_type="look",
        title=title,
        category=category,
        description="Описание.",
        season=["summer"],
        main_color=color,
        style_archetype=["classic"],
        designer_attributes={"fit": "прямой"},
        confidence=0.9,
        designer_reasoning="Комментарий стилиста.",
    )


def make_upload() -> Upload:
    return Upload(
        id=uuid4(),
        user_id=uuid4(),
        source=UploadSource.MINIAPP.value,
        upload_type="auto",
        status=ProcessingStatus.QUEUED.value,
        original_image_id=uuid4(),
    )


class FakeResult:
    def __init__(self, value: Any = None, items: list[Any] | None = None) -> None:
        self.value = value
        self.items = items or []

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalars(self) -> Any:
        return iter(self.items)


class FakeNested:
    async def __aenter__(self) -> "FakeNested":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeSession:
    def __init__(self, upload: Upload, telegram_id: int | None = 777) -> None:
        self.upload = upload
        self.telegram_id = telegram_id
        self.added: list[Any] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, query: Any) -> FakeResult:
        descriptions = getattr(query, "column_descriptions", None)
        if not descriptions:
            return FakeResult()
        entity = descriptions[0].get("entity")
        if entity is Upload:
            return FakeResult(self.upload)
        if entity is GarmentItem:
            return FakeResult(items=[obj for obj in self.added if isinstance(obj, GarmentItem)])
        if entity is User:
            return FakeResult(self.telegram_id)
        return FakeResult()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)

    def begin_nested(self) -> FakeNested:
        return FakeNested()

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    session: FakeSession,
    analysis: LookAnalysis,
    product_image_error: Exception | None = None,
) -> dict[str, Any]:
    recorded: dict[str, Any] = {"stored_keys": [], "notifications": []}

    async def fake_analyze(_self: Any, _image_url: str) -> LookAnalysis:
        return analysis

    async def fake_generate(_self: Any, _image_url: str, _hint: str, _background: str = "white") -> bytes:
        if product_image_error is not None:
            raise product_image_error
        return b"\x89PNG-product"

    async def fake_put_bytes(_self: Any, storage_key: str, _content: bytes, _content_type: str) -> None:
        recorded["stored_keys"].append(storage_key)

    monkeypatch.setattr("aiwardrobe_worker.tasks.get_settings", lambda: SETTINGS)
    monkeypatch.setattr("aiwardrobe_worker.tasks.get_session_factory", lambda: lambda: session)
    monkeypatch.setattr("aiwardrobe_worker.tasks.LlmGateway.analyze_image_items", fake_analyze)
    monkeypatch.setattr("aiwardrobe_worker.tasks.LlmGateway.generate_product_image", fake_generate)
    monkeypatch.setattr("aiwardrobe_core.storage.ObjectStorage.put_bytes", fake_put_bytes)
    monkeypatch.setattr(
        "aiwardrobe_worker.tasks.send_notification.delay",
        lambda telegram_id, text: recorded["notifications"].append((telegram_id, text)),
    )
    return recorded


def test_look_photo_creates_card_per_garment_and_one_look(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_upload()
    session = FakeSession(upload)
    analysis = LookAnalysis(
        image_type="look",
        look_title="Классика",
        look_summary="Синий и бежевый.",
        look_style_tags=["classic"],
        items=[
            make_garment("Синий двубортный пиджак", "outerwear"),
            make_garment("Бежевые брюки", "bottom", "бежевый"),
        ],
    )
    recorded = patch_pipeline(monkeypatch, session, analysis)

    result = analyze_upload.run(str(upload.id), "https://cdn.example/photo.jpg")

    items = [obj for obj in session.added if isinstance(obj, GarmentItem)]
    looks = [obj for obj in session.added if isinstance(obj, LookCard)]
    look_items = [obj for obj in session.added if isinstance(obj, LookItem)]
    processed = [obj for obj in session.added if isinstance(obj, ImageAsset)]

    assert result["items_created"] == 2
    assert [item.title for item in items] == ["Синий двубортный пиджак", "Бежевые брюки"]
    assert len(looks) == 1
    assert looks[0].title == "Классика"
    assert {link.item_id for link in look_items} == {item.id for item in items}
    assert len(processed) == 2
    assert all(item.processed_image_id is not None for item in items)
    assert upload.status == ProcessingStatus.COMPLETED.value
    assert recorded["notifications"] == []


def test_single_item_photo_creates_no_look(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_upload()
    session = FakeSession(upload)
    analysis = LookAnalysis(image_type="item", items=[make_garment("Синяя футболка")])
    patch_pipeline(monkeypatch, session, analysis)

    result = analyze_upload.run(str(upload.id), "https://cdn.example/photo.jpg")

    assert result["items_created"] == 1
    assert [obj for obj in session.added if isinstance(obj, LookCard)] == []
    assert [obj for obj in session.added if isinstance(obj, LookItem)] == []


def test_failed_product_photo_keeps_item_and_notifies_user(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_upload()
    session = FakeSession(upload)
    analysis = LookAnalysis(
        image_type="look",
        items=[make_garment("Синий пиджак", "outerwear"), make_garment("Бежевые брюки", "bottom", "бежевый")],
    )
    recorded = patch_pipeline(monkeypatch, session, analysis, product_image_error=LlmGatewayError("no image"))

    result = analyze_upload.run(str(upload.id), "https://cdn.example/photo.jpg")

    items = [obj for obj in session.added if isinstance(obj, GarmentItem)]
    assert result["items_created"] == 2
    assert all(item.processed_image_id is None for item in items)
    assert upload.status == ProcessingStatus.COMPLETED.value
    assert len(recorded["notifications"]) == 1
    telegram_id, text = recorded["notifications"][0]
    assert telegram_id == 777
    assert "товарное фото" in text
    assert "Синий пиджак" in text and "Бежевые брюки" in text


def test_more_than_six_garments_are_capped_with_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_upload()
    session = FakeSession(upload)
    analysis = LookAnalysis(
        image_type="look",
        items=[make_garment(f"Вещь {index}") for index in range(7)],
    )
    recorded = patch_pipeline(monkeypatch, session, analysis)

    result = analyze_upload.run(str(upload.id), "https://cdn.example/photo.jpg")

    assert result["items_created"] == 6
    assert len(recorded["notifications"]) == 1
    assert "первые 6" in recorded["notifications"][0][1]


def test_completed_upload_is_not_reprocessed(monkeypatch: pytest.MonkeyPatch) -> None:
    upload = make_upload()
    upload.status = ProcessingStatus.COMPLETED.value
    session = FakeSession(upload)
    analysis = LookAnalysis(image_type="item", items=[make_garment("Синяя футболка")])
    patch_pipeline(monkeypatch, session, analysis)

    result = analyze_upload.run(str(upload.id), "https://cdn.example/photo.jpg")

    assert result["skipped"] == "already_completed"
    assert session.commits == 0
    assert [obj for obj in session.added if isinstance(obj, GarmentItem)] == []


def test_find_possible_duplicate_matches_same_and_similar_titles() -> None:
    existing = [
        GarmentItem(
            id=uuid4(), user_id=uuid4(), title="Синий двубортный пиджак", category="outerwear", main_color="синий"
        ),
        GarmentItem(id=uuid4(), user_id=uuid4(), title="Чёрные кроссовки", category="shoes", main_color="чёрный"),
    ]

    assert find_possible_duplicate("синий двубортный пиджак", "outerwear", "синий", existing) is existing[0]
    assert find_possible_duplicate("Пиджак", "outerwear", "синий", existing) is existing[0]
    assert find_possible_duplicate("Белая рубашка", "top", "белый", existing) is None
    assert find_possible_duplicate("Кроссовки", "shoes", "белый", existing) is None

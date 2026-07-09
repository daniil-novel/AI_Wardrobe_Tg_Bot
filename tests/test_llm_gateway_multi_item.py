import json
from base64 import b64encode
from typing import Any

import httpx
import pytest
from aiwardrobe_core.config import Settings
from aiwardrobe_core.llm_gateway import (
    PRODUCT_IMAGE_PROMPT,
    LlmGateway,
    LlmGatewayError,
)

GARMENT_PAYLOAD = {
    "image_type": "item",
    "title": "Синий двубортный пиджак",
    "category": "outerwear",
    "description": "Пиджак из смесовой шерсти.",
    "season": ["spring", "autumn"],
    "main_color": "синий",
    "brand": None,
    "model_name": None,
    "visual_identifiers": ["чёрные пуговицы"],
    "style_archetype": ["classic"],
    "designer_attributes": {"fit": "приталенный"},
    "confidence": 0.9,
    "designer_reasoning": "Хорошо сочетается со светлыми брюками.",
}


def make_fake_client(response_json: dict[str, Any]) -> type:
    class FakeAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: Any) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
            request = httpx.Request("POST", "https://openrouter.test/chat/completions")
            return httpx.Response(200, request=request, json=response_json)

    return FakeAsyncClient


async def test_analyze_image_items_parses_multiple_garments(monkeypatch: pytest.MonkeyPatch) -> None:
    second = {**GARMENT_PAYLOAD, "title": "Бежевые брюки", "category": "bottom", "main_color": "бежевый"}
    content = json.dumps(
        {
            "image_type": "look",
            "look_title": "Классика на манекене",
            "look_summary": "Контраст синего и бежевого.",
            "look_style_tags": ["classic"],
            "items": [GARMENT_PAYLOAD, second],
        }
    )
    monkeypatch.setattr(httpx, "AsyncClient", make_fake_client({"choices": [{"message": {"content": content}}]}))
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test"))

    analysis = await gateway.analyze_image_items("data:image/jpeg;base64,Zm9v")

    assert analysis.image_type == "look"
    assert [item.title for item in analysis.items] == ["Синий двубортный пиджак", "Бежевые брюки"]
    assert analysis.items[1].category == "bottom"


async def test_analyze_image_items_rejects_empty_item_list(monkeypatch: pytest.MonkeyPatch) -> None:
    content = json.dumps({"image_type": "other", "items": []})
    monkeypatch.setattr(httpx, "AsyncClient", make_fake_client({"choices": [{"message": {"content": content}}]}))
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test"))

    with pytest.raises(LlmGatewayError, match="did not detect any garments"):
        await gateway.analyze_image_items("data:image/jpeg;base64,Zm9v")


async def test_generate_product_image_decodes_returned_image(monkeypatch: pytest.MonkeyPatch) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    data_url = f"data:image/png;base64,{b64encode(png_bytes).decode()}"
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        make_fake_client({"choices": [{"message": {"content": "", "images": [{"image_url": {"url": data_url}}]}}]}),
    )
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test"))

    result = await gateway.generate_product_image("data:image/jpeg;base64,Zm9v", "синий пиджак", "white")

    assert result == png_bytes


async def test_generate_product_image_fails_without_image_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        make_fake_client({"choices": [{"message": {"content": "no image", "images": []}}]}),
    )
    gateway = LlmGateway(Settings(openrouter_api_key="sk-test"))

    with pytest.raises(LlmGatewayError, match="no product image"):
        await gateway.generate_product_image("data:image/jpeg;base64,Zm9v", "синий пиджак", "white")


def test_product_image_prompt_keeps_marketplace_and_anti_hallucination_rules() -> None:
    prompt = PRODUCT_IMAGE_PROMPT.format(garment_hint="test", background="pure white background")

    for required in (
        "FORBIDDEN",
        "changing the garment color",
        "removing or hiding defects",
        "smoothing the fabric texture",
        "person, body part or mannequin",
        "decorative",
        "real product card",
    ):
        assert required in prompt

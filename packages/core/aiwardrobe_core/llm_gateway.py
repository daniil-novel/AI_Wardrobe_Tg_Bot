import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from aiwardrobe_core.config import Settings, get_settings


class LlmGatewayError(RuntimeError):
    pass


GARMENT_ANALYSIS_SCHEMA_PROMPT = (
    "Return ONLY a JSON object with exactly these fields: "
    'image_type (string, one of "item", "look", "screenshot", "other"), '
    "title (string, short item name IN RUSSIAN, e.g. «Синяя футболка»), "
    'category (string, EXACTLY one of "top", "bottom", "outerwear", "shoes", "accessory", "dress", "other"), '
    "description (string IN RUSSIAN, 1-2 sentences about the garment only), "
    'season (array of strings from "winter", "spring", "summer", "autumn", "all_season"), '
    "main_color (string IN RUSSIAN, e.g. «синий»), "
    "brand (string or null, visible brand only; use null if not visible), "
    "model_name (string or null, exact visible/recognizable product model only; use null if unsure), "
    "visual_identifiers (array of RUSSIAN strings: logo, stripes, sole shape, fabric cues), "
    'style_archetype (array of strings from "casual", "classic", "sport", "street", "business", "evening"), '
    "designer_attributes (object with any of fit, fabric, pattern, neckline, length as RUSSIAN strings), "
    "confidence (number between 0 and 1), "
    "designer_reasoning (string IN RUSSIAN: why the item works and how to style it). "
    "If brand/model is visible or confidently recognizable, title MUST include it in Russian, for example "
    "«Кроссовки Adidas Samba OG», not generic «Чёрные кроссовки». If model is uncertain, include brand and type "
    "only, and put uncertainty into visual_identifiers. All free-text values must be in Russian; category, season "
    "and style_archetype must use the exact English tokens listed above."
)


def extract_json_object(content: str) -> str:
    """Trim markdown fences or prose around the outermost JSON object."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return content
    return content[start : end + 1]


class GarmentAnalysis(BaseModel):
    image_type: str
    title: str
    category: str
    description: str
    season: list[str]
    main_color: str
    brand: str | None = None
    model_name: str | None = None
    visual_identifiers: list[str] = Field(default_factory=list)
    style_archetype: list[str]
    designer_attributes: dict[str, Any]
    confidence: float
    designer_reasoning: str

    @field_validator("season", "style_archetype", mode="before")
    @classmethod
    def wrap_scalar_in_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> Any:
        if isinstance(value, int | float) and 1 < float(value) <= 100:
            return float(value) / 100
        return value


class LlmGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def analyze_image(self, image_url: str, prompt: str) -> GarmentAnalysis:
        if not self.settings.openrouter_api_key:
            raise LlmGatewayError("OPENROUTER_API_KEY is required for real AI processing.")

        payload = {
            "model": self.settings.openrouter_model_image,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a safe fashion analysis service. Analyze clothing only. "
                        "Do not assess face, body, age, attractiveness, health, or identity. "
                        + GARMENT_ANALYSIS_SCHEMA_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "HTTP-Referer": self.settings.public_api_url,
                    "X-Title": "AI Digital Wardrobe",
                },
                json=payload,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return GarmentAnalysis.model_validate_json(extract_json_object(content))
        except ValidationError as exc:
            raise LlmGatewayError("OpenRouter response failed GarmentAnalysis validation.") from exc

    async def generate_text_json(self, prompt: str, schema_name: str) -> dict[str, Any]:
        if not self.settings.openrouter_api_key:
            raise LlmGatewayError("OPENROUTER_API_KEY is required for real AI processing.")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.openrouter_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openrouter_api_key}"},
                json={
                    "model": self.settings.openrouter_model_text,
                    "messages": [
                        {"role": "system", "content": f"Return strict JSON for {schema_name}."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        content: str = response.json()["choices"][0]["message"]["content"]
        try:
            parsed: Any = json.loads(extract_json_object(content))
        except json.JSONDecodeError as exc:
            raise LlmGatewayError("OpenRouter text response was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise LlmGatewayError("OpenRouter text response was not a JSON object.")
        return parsed

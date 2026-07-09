import json
from base64 import b64decode
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
    "designer_attributes (object with these keys: "
    "fit, fabric, pattern, neckline, length as RUSSIAN strings; "
    "warmth_level as integer 1-5 where 1 is very light and 5 is very warm; "
    'temperature_range as RUSSIAN string like "+10…+20°C"; '
    "formality as integer 1-5; "
    "silhouette as RUSSIAN string; "
    'palette_role as one of "base", "neutral", "accent", "statement"; '
    "wear_with as array of 2-4 RUSSIAN strings — with what to combine; "
    "avoid_with as array of 0-3 RUSSIAN strings — what to avoid combining), "
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


LOOK_ANALYSIS_SCHEMA_PROMPT = (
    "You will receive one photo. It may show a single garment, a full outfit (look), a selfie or "
    "a mirror photo of a person, or a store screenshot. Detect EVERY distinct clothing item and "
    "visible footwear/accessory (max 6). Never describe or evaluate the person, face or body — "
    "clothing only. Return ONLY a JSON object with fields: "
    'image_type (string, one of "item", "look", "screenshot", "other" — use "look" when a person '
    "is wearing the clothes or several garments form an outfit), "
    "look_title (string IN RUSSIAN, short outfit name, e.g. «Кэжуал на прохладный день»), "
    "look_summary (string IN RUSSIAN: 1-3 sentences on why this look works stylistically), "
    'look_style_tags (array of strings from "casual", "classic", "sport", "street", "business", "evening"), '
    "items (array where EACH element is an object with exactly the fields described next). "
    "Each item object: "
    + GARMENT_ANALYSIS_SCHEMA_PROMPT.replace("Return ONLY a JSON object with exactly these fields: ", "")
)


PRODUCT_IMAGE_PROMPT = (
    "You are a product-photo extraction agent: garment segmentation, distortion-free retouch, "
    "marketplace-style product cards (Wildberries/Ozon). "
    "TASK: from the input photo isolate exactly one target garment — {garment_hint} — and render it "
    "as a clean e-commerce product photo: the garment alone, neatly presented, centered on a "
    "{background}, soft studio light, subtle natural shadow. "
    "PRESERVE EXACTLY: color, cut, shape, proportions, fit, fabric texture, pattern, prints, logos, "
    "stitching, hardware, and every real defect or customization — holes, stains, scuffs, fading, "
    "wrinkles, repairs, custom paint. Reconstruct areas hidden by the person, mannequin or other "
    "objects only minimally and logically, without inventing new details. "
    "FORBIDDEN: changing the garment color; altering cut, shape or proportions; removing or hiding "
    "defects and custom elements; adding design elements, logos, prints or seams absent from the "
    "photo; smoothing the fabric texture; replacing the material; leaving any person, body part or "
    "mannequin in frame; keeping the original background or using a decorative one; adding text or "
    "watermarks. "
    "The result must look like a real product card of this exact physical item. "
    "When unsure, keep the source visual information unchanged."
)


class LookAnalysis(BaseModel):
    image_type: str = "item"
    look_title: str = "Загруженный образ"
    look_summary: str = ""
    look_style_tags: list[str] = Field(default_factory=list)
    items: list[GarmentAnalysis] = Field(default_factory=list)

    @field_validator("look_style_tags", mode="before")
    @classmethod
    def wrap_tags(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        return value or []


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

    async def analyze_image_items(self, image_url: str) -> LookAnalysis:
        """Detect every garment on the photo (single item, look or selfie) as separate cards."""
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
                        + LOOK_ANALYSIS_SCHEMA_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Разбери фото на отдельные вещи и верни строгий JSON по схеме.",
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
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
            analysis = LookAnalysis.model_validate_json(extract_json_object(content))
        except ValidationError as exc:
            raise LlmGatewayError("OpenRouter response failed LookAnalysis validation.") from exc
        if not analysis.items:
            raise LlmGatewayError("OpenRouter did not detect any garments on the photo.")
        return analysis

    async def generate_product_image(
        self, source_image_url: str, garment_hint: str, background: str = "white"
    ) -> bytes:
        """Extract the garment from the photo into a clean product shot via an image model."""
        if not self.settings.openrouter_api_key:
            raise LlmGatewayError("OPENROUTER_API_KEY is required for product image generation.")
        background_note = "pure white background" if background == "white" else "dark charcoal studio background"
        payload = {
            "model": self.settings.openrouter_model_image_gen,
            "modalities": ["image", "text"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": PRODUCT_IMAGE_PROMPT.format(garment_hint=garment_hint, background=background_note),
                        },
                        {"type": "image_url", "image_url": {"url": source_image_url}},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=120) as client:
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
        message = response.json()["choices"][0]["message"]
        images = message.get("images") or []
        if not images:
            raise LlmGatewayError("Image model returned no product image.")
        data_url = str(images[0].get("image_url", {}).get("url", ""))
        if not data_url.startswith("data:image"):
            raise LlmGatewayError("Image model returned an unexpected payload.")
        return b64decode(data_url.split(",", 1)[1])

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

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from aiwardrobe_core.config import Settings, get_settings


class LlmGatewayError(RuntimeError):
    pass


class GarmentAnalysis(BaseModel):
    image_type: str
    title: str
    category: str
    description: str
    season: list[str]
    main_color: str
    style_archetype: list[str]
    designer_attributes: dict[str, Any]
    confidence: float
    designer_reasoning: str


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
                        "Return strict JSON matching the requested schema. Do not assess face, body, "
                        "age, attractiveness, health, or identity."
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
            return GarmentAnalysis.model_validate_json(content)
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
        parsed: Any = httpx.Response(200, content=content).json()
        if not isinstance(parsed, dict):
            raise LlmGatewayError("OpenRouter text response was not a JSON object.")
        return parsed

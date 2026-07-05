"""Open-Meteo weather client: free, keyless, good enough for outfit context."""

from typing import Any

import httpx
from pydantic import BaseModel

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODE_RU = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    56: "ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "кратковременный дождь",
    81: "ливень",
    82: "сильный ливень",
    85: "небольшой снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}


class WeatherSummary(BaseModel):
    temperature_c: float
    feels_like_c: float
    temperature_min_c: float
    temperature_max_c: float
    precipitation_probability: int
    wind_speed_ms: float
    condition: str
    summary: str

    def context_line(self) -> str:
        """Compact single-line weather context for AI prompts."""
        return (
            f"{self.condition}, сейчас {self.temperature_c:.0f}°C (ощущается {self.feels_like_c:.0f}°C), "
            f"днём {self.temperature_min_c:.0f}..{self.temperature_max_c:.0f}°C, "
            f"вероятность осадков {self.precipitation_probability}%, ветер {self.wind_speed_ms:.0f} м/с"
        )


def parse_open_meteo(payload: dict[str, Any]) -> WeatherSummary:
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    code = int(current.get("weather_code", 3))
    condition = WEATHER_CODE_RU.get(code, "облачно")
    temperature = float(current.get("temperature_2m", 0.0))
    feels_like = float(current.get("apparent_temperature", temperature))
    temp_min = float((daily.get("temperature_2m_min") or [temperature])[0])
    temp_max = float((daily.get("temperature_2m_max") or [temperature])[0])
    precipitation = int((daily.get("precipitation_probability_max") or [0])[0] or 0)
    wind = float(current.get("wind_speed_10m", 0.0))

    parts = [f"Сейчас {temperature:.0f}°C, {condition}"]
    if abs(feels_like - temperature) >= 2:
        parts.append(f"ощущается как {feels_like:.0f}°C")
    parts.append(f"днём от {temp_min:.0f}°C до {temp_max:.0f}°C")
    if precipitation >= 30:
        parts.append(f"осадки с вероятностью {precipitation}%")
    if wind >= 8:
        parts.append(f"сильный ветер {wind:.0f} м/с")

    return WeatherSummary(
        temperature_c=temperature,
        feels_like_c=feels_like,
        temperature_min_c=temp_min,
        temperature_max_c=temp_max,
        precipitation_probability=precipitation,
        wind_speed_ms=wind,
        condition=condition,
        summary=", ".join(parts) + ".",
    )


async def fetch_weather(latitude: float, longitude: float) -> WeatherSummary:
    params: dict[str, str | int | float] = {
        "latitude": round(latitude, 4),
        "longitude": round(longitude, 4),
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "forecast_days": 1,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        return parse_open_meteo(response.json())

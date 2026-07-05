from uuid import uuid4

from aiwardrobe_api.dependencies import get_current_user
from aiwardrobe_api.main import create_app
from aiwardrobe_api.routers import weather as weather_router
from aiwardrobe_core.weather import WeatherSummary, parse_open_meteo
from fastapi.testclient import TestClient


class FakeWeatherRedis:
    def __init__(self, cached: WeatherSummary | None = None) -> None:
        self.cached = cached
        self.written: tuple[str, str, int] | None = None

    async def get(self, key: str) -> str | None:
        _ = key
        return self.cached.model_dump_json() if self.cached else None

    async def set(self, key: str, value: str, ex: int) -> None:
        self.written = (key, value, ex)


def test_parse_open_meteo_returns_russian_summary() -> None:
    summary = parse_open_meteo(
        {
            "current": {
                "temperature_2m": 12,
                "apparent_temperature": 9,
                "weather_code": 61,
                "wind_speed_10m": 9,
            },
            "daily": {
                "temperature_2m_min": [7],
                "temperature_2m_max": [14],
                "precipitation_probability_max": [70],
            },
        }
    )

    assert summary.condition == "небольшой дождь"
    assert "ощущается как 9°C" in summary.summary
    assert "осадки с вероятностью 70%" in summary.summary
    assert "ветер 9 м/с" in summary.context_line()


def test_weather_route_returns_cached_summary(monkeypatch) -> None:
    cached = WeatherSummary(
        temperature_c=18,
        feels_like_c=17,
        temperature_min_c=13,
        temperature_max_c=21,
        precipitation_probability=20,
        wind_speed_ms=4,
        condition="облачно",
        summary="Сейчас 18°C, облачно.",
    )
    monkeypatch.setattr(weather_router, "_get_redis", lambda: FakeWeatherRedis(cached))
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: uuid4()
    client = TestClient(app)

    response = client.get("/weather?latitude=55.75&longitude=37.62")

    assert response.status_code == 200
    assert response.json()["summary"] == "Сейчас 18°C, облачно."


def test_weather_route_fetches_and_caches_summary(monkeypatch) -> None:
    redis = FakeWeatherRedis()
    fetched = WeatherSummary(
        temperature_c=5,
        feels_like_c=2,
        temperature_min_c=1,
        temperature_max_c=7,
        precipitation_probability=45,
        wind_speed_ms=6,
        condition="дождь",
        summary="Сейчас 5°C, дождь.",
    )

    async def fake_fetch_weather(latitude: float, longitude: float) -> WeatherSummary:
        assert latitude == 55.75
        assert longitude == 37.62
        return fetched

    monkeypatch.setattr(weather_router, "_get_redis", lambda: redis)
    monkeypatch.setattr(weather_router, "fetch_weather", fake_fetch_weather)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: uuid4()
    client = TestClient(app)

    response = client.get("/weather?latitude=55.75&longitude=37.62")

    assert response.status_code == 200
    assert response.json()["condition"] == "дождь"
    assert redis.written is not None
    assert redis.written[2] == weather_router.CACHE_TTL_SECONDS

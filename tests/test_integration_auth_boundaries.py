from aiwardrobe_api.main import create_app
from fastapi.testclient import TestClient


def test_user_data_routes_are_protected_integration() -> None:
    client = TestClient(create_app())

    protected_routes = [
        ("GET", "/items"),
        ("GET", "/looks"),
        ("GET", "/outfits"),
        ("GET", "/wishlist"),
        ("GET", "/style-dna"),
        ("GET", "/wardrobe/health"),
        ("GET", "/ai/usage"),
    ]

    for method, path in protected_routes:
        response = client.request(method, path)
        assert response.status_code == 401, path


def test_observability_endpoints_are_public_integration() -> None:
    client = TestClient(create_app())

    live = client.get("/health/live")
    metrics = client.get("/metrics")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert metrics.status_code == 200
    assert "aiwardrobe_app_info" in metrics.text

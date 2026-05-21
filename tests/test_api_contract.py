from aiwardrobe_api.main import create_app
from fastapi.testclient import TestClient


def test_root_route_explains_local_api() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "AI Digital Wardrobe API"
    assert payload["docs_url"] == "/docs"
    assert "uploads" in payload["api_groups"]


def test_health_route_reports_runtime_secret_state() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "missing_runtime_secrets" in payload


def test_core_endpoint_groups_are_available() -> None:
    client = TestClient(create_app())

    checks = {
        "/items": 401,
        "/looks": 401,
        "/outfits": 401,
        "/style-dna": 401,
        "/wardrobe/health": 401,
        "/wishlist": 401,
        "/billing/plans": 200,
        "/ai/usage": 401,
    }
    for path, expected_status in checks.items():
        response = client.get(path)
        assert response.status_code == expected_status, path


def test_openrouter_real_mode_is_explicit_when_key_is_missing() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/ai/analyze-image",
        json={"upload_id": "00000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 401


def test_upload_photo_lifecycle_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/uploads/file?upload_type=item",
        files={"file": ("shirt.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 401


def test_upload_photo_rejects_anonymous_non_images_before_processing() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/uploads/file?upload_type=item",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 401

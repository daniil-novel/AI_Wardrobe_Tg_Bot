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
        "/items": 200,
        "/looks": 200,
        "/outfits": 200,
        "/style-dna": 200,
        "/wardrobe/health": 200,
        "/wishlist": 200,
        "/billing/plans": 200,
        "/ai/usage": 200,
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

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_upload_photo_lifecycle_accepts_image_files() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/uploads/file?upload_type=item",
        files={"file": ("shirt.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["progress"] == 25
    assert payload["filename"] == "shirt.jpg"
    assert payload["upload_type"] == "item"

    upload_id = payload["id"]
    status_response = client.get(f"/uploads/{upload_id}")
    assert status_response.status_code == 200
    assert status_response.json()["id"] == upload_id

    retry_response = client.post(f"/uploads/{upload_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "queued"

    delete_response = client.delete(f"/uploads/{upload_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_upload_photo_rejects_non_images() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/uploads/file?upload_type=item",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400

"""Contract smoke tests for the local HTTP adapter."""

from fastapi.testclient import TestClient

from mercosul_anpr.api.app import app


def test_health_version_home_and_openapi() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/version").json()["version"] == "0.1.0"
        assert "Mercosul ANPR" in client.get("/").text
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/jobs" in paths
        assert "/api/v1/process/image" in paths


def test_rejects_unsupported_upload_without_loading_models() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs", files={"file": ("payload.exe", b"invalid")})
    assert response.status_code == 415

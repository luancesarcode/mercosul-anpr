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
        assert "/api/v1/realtime/sessions" in paths
        assert "/api/v1/realtime/sessions/{session_id}/frames" in paths


def test_rejects_unsupported_upload_without_loading_models() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs", files={"file": ("payload.exe", b"invalid")})
    assert response.status_code == 415


def test_realtime_http_contract_without_loading_models(monkeypatch) -> None:
    realtime = app.state.realtime_manager
    session_payload = {
        "id": "camera-test",
        "status": "ready",
        "expires_in_seconds": 300,
        "frame_url": "/api/v1/realtime/sessions/camera-test/frames",
        "close_url": "/api/v1/realtime/sessions/camera-test",
    }
    frame_payload = {
        "session_id": "camera-test",
        "frame": 1,
        "vehicles": 0,
        "plates": [],
        "elapsed_ms": 10.0,
        "inference_fps": 100.0,
        "stage_ms": {},
        "annotated_image": "data:image/jpeg;base64,/9j/",
    }
    monkeypatch.setattr(realtime, "create_session", lambda: session_payload)
    monkeypatch.setattr(realtime, "process_frame", lambda session_id, payload: frame_payload)
    monkeypatch.setattr(realtime, "close_session", lambda session_id: session_id == "camera-test")

    with TestClient(app) as client:
        created = client.post("/api/v1/realtime/sessions")
        frame = client.post(
            "/api/v1/realtime/sessions/camera-test/frames",
            files={"file": ("camera-frame.jpg", b"jpeg", "image/jpeg")},
        )
        closed = client.delete("/api/v1/realtime/sessions/camera-test")

    assert created.status_code == 201
    assert created.json()["id"] == "camera-test"
    assert frame.status_code == 200
    assert frame.json()["frame"] == 1
    assert closed.status_code == 204


def test_realtime_rejects_non_image_frame_before_inference() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/realtime/sessions/missing/frames",
            files={"file": ("frame.txt", b"invalid", "text/plain")},
        )
    assert response.status_code == 415

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_landing_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Blip" in response.text

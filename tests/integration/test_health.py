from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Financial Recommender"


def test_system_info() -> None:
    response = client.get("/v1/system/info")
    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "Financial Recommender"
    assert "version" in body
    assert "author_name" in body
    assert "author_url" in body

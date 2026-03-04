from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_admin_login_success() -> None:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "passw0rd"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_admin_login_failure() -> None:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401

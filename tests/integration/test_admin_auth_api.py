import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_BOOTSTRAP_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin-test-password")


def test_admin_login_success() -> None:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": ADMIN_BOOTSTRAP_USERNAME, "password": ADMIN_BOOTSTRAP_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert body["username"] == ADMIN_BOOTSTRAP_USERNAME
    assert body["role"] == "admin"


def test_admin_login_failure() -> None:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": ADMIN_BOOTSTRAP_USERNAME, "password": "wrong-password"},
    )
    assert response.status_code == 401

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_BOOTSTRAP_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin-test-password")
TEST_USER_PASSWORD = "test-user-password-1"


def _login(username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_alert_subscription_crud_flow() -> None:
    headers = _login(ADMIN_BOOTSTRAP_USERNAME, ADMIN_BOOTSTRAP_PASSWORD)
    create_response = client.post(
        "/v1/admin/alerts/subscriptions",
        headers=headers,
        json={
            "symbol": "AAPL",
            "asset_type": "stock",
            "alert_scope": "technical",
            "metric": "rsi_14",
            "operator": "<=",
            "threshold": 30.0,
            "notes": "test-alert",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    subscription_id = int(created["id"])
    assert created["symbol"] == "AAPL"

    list_response = client.get("/v1/admin/alerts/subscriptions", headers=headers)
    assert list_response.status_code == 200
    assert any(int(item["id"]) == subscription_id for item in list_response.json())

    update_response = client.patch(
        f"/v1/admin/alerts/subscriptions/{subscription_id}",
        headers=headers,
        json={
            "metric": "macd",
            "operator": ">=",
            "threshold": 0.0,
            "is_active": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["metric"] == "macd"

    delete_response = client.delete(
        f"/v1/admin/alerts/subscriptions/{subscription_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200


def test_user_requires_active_subscription_for_alerts() -> None:
    admin_headers = _login(ADMIN_BOOTSTRAP_USERNAME, ADMIN_BOOTSTRAP_PASSWORD)
    username = f"user_{uuid4().hex[:10]}"
    email = f"{username}@example.com"
    create_user = client.post(
        "/v1/admin/users",
        headers=admin_headers,
        json={
            "username": username,
            "email": email,
            "password": TEST_USER_PASSWORD,
            "role": "user",
            "is_active": True,
        },
    )
    assert create_user.status_code == 200
    user_id = int(create_user.json()["id"])

    user_headers = _login(username, TEST_USER_PASSWORD)
    denied = client.get("/v1/admin/alerts/subscriptions", headers=user_headers)
    assert denied.status_code == 403

    future_date = (datetime.now(UTC) + timedelta(days=15)).replace(tzinfo=None).isoformat()
    update_user = client.patch(
        f"/v1/admin/users/{user_id}",
        headers=admin_headers,
        json={"subscription_ends_at": future_date},
    )
    assert update_user.status_code == 200

    user_headers = _login(username, TEST_USER_PASSWORD)
    allowed = client.get("/v1/admin/alerts/subscriptions", headers=user_headers)
    assert allowed.status_code == 200

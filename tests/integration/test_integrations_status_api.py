from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_integrations_status_endpoint() -> None:
    response = client.get("/v1/integrations/status")
    assert response.status_code == 200
    body = response.json()
    assert "overall" in body
    assert "checked_at" in body
    assert isinstance(body.get("integrations"), list)
    assert any(item.get("key") == "alphavantage_mcp" for item in body["integrations"])
    assert any(item.get("key") == "chart_img" for item in body["integrations"])
    assert any(item.get("key") == "coinmarketcap" for item in body["integrations"])
    assert any(item.get("key") == "alert_daemon" for item in body["integrations"])

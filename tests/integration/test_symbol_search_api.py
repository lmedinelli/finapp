from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_symbol_search_endpoint() -> None:
    response = client.get("/v1/market/symbol-search?q=apple")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(item.get("symbol") == "AAPL" for item in body)


def test_symbol_search_endpoint_without_query() -> None:
    response = client.get("/v1/market/symbol-search")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0

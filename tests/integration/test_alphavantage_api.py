from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_alphavantage_context_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.alphavantage_service,
        "get_market_context",
        lambda symbol: {
            "symbol": symbol,
            "quote": {
                "symbol": symbol,
                "price": 200.0,
                "change_percent": 1.2,
                "volume": 1200000.0,
                "latest_trading_day": "2026-03-02",
            },
            "trend": {
                "direction": "uptrend",
                "change_pct_30d": 3.5,
                "sma_20": 190.0,
                "sma_50": 180.0,
            },
            "candles": [],
            "news": [],
            "source": "alphavantage-mcp",
        },
    )

    response = client.get("/v1/market/alphavantage/context/AAPL?asset_type=stock")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["trend"]["direction"] == "uptrend"

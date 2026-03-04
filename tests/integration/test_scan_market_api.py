from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_scan_the_market_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.scan_the_market_service,
        "scan",
        lambda **kwargs: {
            "scan_id": "scan-1",
            "generated_at": "2026-03-03T00:00:00Z",
            "low_cap_max_usd": kwargs.get("low_cap_max_usd", 2_000_000_000.0),
            "stock_opportunities": [
                {
                    "symbol": "SOFI",
                    "name": "SoFi Technologies",
                    "asset_type": "stock",
                    "market_cap": 9_000_000_000.0,
                    "price": 8.2,
                    "change_pct": 1.1,
                    "volume": 1_000_000.0,
                    "momentum_30d": 12.3,
                    "score": 2.5,
                    "rationale": "mock",
                    "source": "mock",
                }
            ],
            "crypto_opportunities": [],
            "ipo_watchlist": [],
            "ico_watchlist": [],
            "news_signals": [],
            "data_sources": ["yfinance"],
            "warnings": [],
        },
    )

    response = client.post(
        "/v1/scan/the-market",
        json={
            "low_cap_max_usd": 10_000_000_000.0,
            "stock_limit": 5,
            "crypto_limit": 5,
            "include_ipo": True,
            "include_ico": True,
            "include_news": True,
            "exchanges": ["NASDAQ"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == "scan-1"
    assert body["stock_opportunities"][0]["symbol"] == "SOFI"

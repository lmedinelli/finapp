from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_market_snapshot_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.market_snapshot_service,
        "compute",
        lambda symbol, asset_type, period, interval, metrics: {
            "symbol": "AAPL",
            "asset_type": "stock",
            "period": period,
            "interval": interval,
            "sample_size": 50,
            "last_timestamp": "2026-03-02T00:00:00",
            "history_points": 5,
            "history_labels": [
                "2026-02-25",
                "2026-02-26",
                "2026-02-27",
                "2026-02-28",
                "2026-03-02",
            ],
            "selected_metrics": [
                {
                    "metric": "sma_20",
                    "value": 195.2,
                    "history": [
                        {"label": "2026-02-25", "timestamp": "2026-02-25T00:00:00", "value": 191.0},
                        {"label": "2026-02-26", "timestamp": "2026-02-26T00:00:00", "value": 191.8},
                        {"label": "2026-02-27", "timestamp": "2026-02-27T00:00:00", "value": 192.1},
                        {"label": "2026-02-28", "timestamp": "2026-02-28T00:00:00", "value": 193.7},
                        {"label": "2026-03-02", "timestamp": "2026-03-02T00:00:00", "value": 195.2},
                    ],
                    "trend_status": "improving",
                    "trend_delta": 4.2,
                }
            ],
            "available_metrics": ["sma_20", "sma_50"],
        },
    )

    response = client.get(
        "/v1/market/snapshot/AAPL",
        params={"asset_type": "stock", "period": "6mo", "interval": "1d", "metrics": "sma_20"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["history_points"] == 5
    assert body["selected_metrics"][0]["metric"] == "sma_20"
    assert body["selected_metrics"][0]["trend_status"] == "improving"

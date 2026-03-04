from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_news_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.news_service,
        "fetch_news",
        lambda symbol, asset_type="stock": [
            {
                "title": "AAPL bullish outlook",
                "url": "https://example.com",
                "source": "Example",
                "published_at": "today",
            }
        ],
    )
    monkeypatch.setattr(
        api_router.news_service,
        "sentiment_summary",
        lambda headlines: {
            "score": 0.2,
            "label": "positive",
            "sample_size": len(headlines),
            "generated_at": "2026-03-02T00:00:00",
        },
    )

    response = client.get("/v1/news/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["sentiment"]["label"] == "positive"

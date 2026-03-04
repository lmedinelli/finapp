from types import SimpleNamespace

from app.services.news import NewsService


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._payload


def test_fetch_news_parses_serpapi_payload(monkeypatch) -> None:
    service = NewsService()
    service.settings = SimpleNamespace(
        serpapi_api_key="test-key",
        serpapi_endpoint="https://serpapi.com/search.json",
        news_max_items=3,
    )

    payload = {
        "news_results": [
            {
                "title": "AAPL posts record growth",
                "link": "https://example.com/aapl-growth",
                "source": {"name": "Example"},
                "date": "1 hour ago",
            },
            {
                "title": "AAPL upgrade drives rally",
                "link": "https://example.com/aapl-upgrade",
                "source": "Reuters",
                "date": "2 hours ago",
            },
        ]
    }

    def fake_get(url: str, params: dict, timeout: float) -> DummyResponse:
        assert url == "https://serpapi.com/search.json"
        assert params["engine"] == "google_news"
        assert params["api_key"] == "test-key"
        assert timeout == 15.0
        return DummyResponse(payload)

    monkeypatch.setattr("app.services.news.httpx.get", fake_get)
    result = service.fetch_news("AAPL", asset_type="stock", limit=2)

    assert len(result) == 2
    assert result[0]["title"] == "AAPL posts record growth"
    assert result[1]["source"] == "Reuters"


def test_fetch_news_returns_empty_without_key() -> None:
    service = NewsService()
    service.settings = SimpleNamespace(
        serpapi_api_key="",
        serpapi_endpoint="https://serpapi.com/search.json",
        news_max_items=3,
    )
    result = service.fetch_news("AAPL")
    assert result == []

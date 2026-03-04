import os

import pytest

from app.services.news import NewsService


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_SERPAPI_TESTS") or not os.getenv("SERPAPI_API_KEY"),
    reason="Set RUN_LIVE_SERPAPI_TESTS=1 and SERPAPI_API_KEY to run live test",
)
def test_serpapi_live_news_fetch() -> None:
    service = NewsService()
    headlines = service.fetch_news(symbol="AAPL", asset_type="stock", limit=3)
    assert isinstance(headlines, list)

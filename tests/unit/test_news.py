from app.services.news import NewsService


def test_sentiment_summary_positive() -> None:
    headlines = [
        {"title": "AAPL beats estimates with record growth"},
        {"title": "AAPL expands partnership and reports strong demand"},
    ]
    summary = NewsService.sentiment_summary(headlines)
    assert summary["label"] == "positive"
    assert summary["sample_size"] == 2


def test_sentiment_summary_neutral_for_empty() -> None:
    summary = NewsService.sentiment_summary([])
    assert summary["label"] == "neutral"
    assert summary["score"] == 0.0

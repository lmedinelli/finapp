from app.services.recommendation import RecommendationService


class DummyAnalytics:
    def compute(self, symbol: str) -> dict[str, float | str]:
        return {
            "symbol": symbol,
            "latest_close": 120.0,
            "sma_20": 118.0,
            "sma_50": 115.0,
            "sma_200": 100.0,
            "volatility_30d": 0.22,
            "momentum_30d": 0.08,
            "momentum_90d": 0.18,
            "rsi_14": 58.0,
            "macd": 1.2,
            "macd_signal": 0.9,
            "atr_14": 2.0,
            "bollinger_upper": 125.0,
            "bollinger_lower": 110.0,
            "support_60d": 109.0,
            "resistance_60d": 124.0,
            "trend_strength": 0.02,
            "signal_short_term": "bullish",
            "signal_long_term": "bullish",
            "signal": "bullish",
        }


class DummyNews:
    def fetch_news(
        self,
        symbol: str,
        asset_type: str = "stock",
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        return [
            {
                "title": "Company posts strong growth",
                "url": "",
                "source": "Example",
                "published_at": "",
            }
        ]

    def sentiment_summary(self, headlines: list[dict[str, str]]) -> dict[str, float | str | int]:
        return {
            "score": 0.5,
            "label": "positive",
            "sample_size": 1,
            "generated_at": "2026-03-02T00:00:00",
        }


def test_recommendation_contains_horizon_actions() -> None:
    service = RecommendationService()
    service.analytics = DummyAnalytics()  # type: ignore[assignment]
    service.news = DummyNews()  # type: ignore[assignment]

    result = service.recommend(symbol="AAPL", risk_profile="balanced", asset_type="stock")
    assert result["recommendation"] in {"buy", "hold", "reduce"}
    assert result["short_term"]["action"] in {"buy", "hold", "reduce"}
    assert result["long_term"]["action"] in {"buy", "hold", "reduce"}
    assert result["news_sentiment"]["label"] == "positive"

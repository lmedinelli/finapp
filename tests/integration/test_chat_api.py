from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    def fake_respond(
        message: str,
        symbol: str | None,
        asset_type: str,
        risk_profile: str,
        session_id: str | None,
        include_news: bool,
        include_alpha_context: bool,
        include_merged_news_sentiment: bool,
    ) -> dict:
        return {
            "session_id": session_id or "test-session",
            "symbol": "AAPL",
            "asset_type": "stock",
            "answer": "AAPL short-term=hold, long-term=buy.",
            "inferred_horizon": "both",
            "recommendation": {
                "symbol": "AAPL",
                "recommendation": "hold",
                "confidence": 0.6,
                "rationale": "mock",
                "short_term": {"action": "hold", "confidence": 0.6, "rationale": "mock"},
                "long_term": {"action": "buy", "confidence": 0.7, "rationale": "mock"},
                "news_sentiment": {
                    "score": 0.1,
                    "label": "neutral",
                    "sample_size": 0,
                    "generated_at": "2026-03-02T00:00:00",
                },
                "news": [],
                "technical_snapshot": {"symbol": "AAPL"},
                "disclaimer": "Decision support only. This is not financial advice.",
            },
            "analysis": {
                "symbol": "AAPL",
                "latest_close": 100.0,
                "sma_20": 99.0,
                "sma_50": 98.0,
                "sma_200": 95.0,
                "volatility_30d": 0.2,
                "momentum_30d": 0.03,
                "momentum_90d": 0.08,
                "rsi_14": 55.0,
                "macd": 1.0,
                "macd_signal": 0.9,
                "atr_14": 2.0,
                "bollinger_upper": 103.0,
                "bollinger_lower": 95.0,
                "support_60d": 94.0,
                "resistance_60d": 104.0,
                "trend_strength": 0.01,
                "signal_short_term": "neutral",
                "signal_long_term": "bullish",
                "signal": "neutral",
            },
            "news": [],
            "market_context": {
                "symbol": "AAPL",
                "quote": {
                    "symbol": "AAPL",
                    "price": 100.0,
                    "change_percent": 0.5,
                    "volume": 1000000,
                    "latest_trading_day": "2026-03-02",
                },
                "trend": {
                    "direction": "uptrend",
                    "change_pct_30d": 4.0,
                    "sma_20": 98.0,
                    "sma_50": 95.0,
                },
                "candles": [],
                "news": [],
                "source": "alphavantage-mcp",
            },
            "disclaimer": "Decision support only. This is not financial advice.",
            "workflow_steps": ["symbol_resolved:AAPL", "tool:analysis_local", "llm:fallback"],
        }

    monkeypatch.setattr(api_router.chat_service, "respond", fake_respond)
    response = client.post(
        "/v1/chat",
        json={"message": "Should I buy AAPL short and long term?", "symbol": "AAPL"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["session_id"] == "test-session"
    assert body["market_context"]["symbol"] == "AAPL"
    assert "answer" in body

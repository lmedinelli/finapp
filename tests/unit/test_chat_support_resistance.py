from __future__ import annotations

from typing import Any

from app.services.chat import ChatService


def _analysis(symbol: str) -> dict[str, float | str]:
    return {
        "symbol": symbol,
        "latest_close": 520.0,
        "sma_20": 515.0,
        "sma_50": 510.0,
        "sma_200": 498.0,
        "volatility_30d": 0.18,
        "momentum_30d": 0.04,
        "momentum_90d": 0.11,
        "rsi_14": 53.0,
        "macd": 1.1,
        "macd_signal": 0.8,
        "atr_14": 4.1,
        "bollinger_upper": 532.0,
        "bollinger_lower": 503.0,
        "support_60d": 500.0,
        "resistance_60d": 530.0,
        "trend_strength": 0.02,
        "signal_short_term": "neutral",
        "signal_long_term": "bullish",
        "signal": "bullish",
    }


def _recommendation() -> dict[str, Any]:
    return {
        "recommendation": "hold",
        "confidence": 0.62,
        "short_term": {"action": "hold", "confidence": 0.58},
        "long_term": {"action": "buy", "confidence": 0.67},
        "rationale": [],
        "news_sentiment": {"score": 0.1, "label": "neutral", "sample_size": 0, "generated_at": ""},
        "news": [],
        "disclaimer": "Decision support only. This is not financial advice.",
    }


def _patch_common(monkeypatch, service: ChatService) -> None:
    monkeypatch.setattr(service, "_load_memory", lambda session_id: [])
    monkeypatch.setattr(service, "_save_memory", lambda session_id, role, content: None)
    monkeypatch.setattr(service.activity_log, "log_recommendation", lambda **kwargs: None)
    monkeypatch.setattr(service.market_data, "normalize_symbol", lambda symbol, asset_type: symbol)
    monkeypatch.setattr(
        service,
        "_compute_or_ingest",
        lambda symbol, asset_type, workflow_steps: _analysis(symbol),
    )
    monkeypatch.setattr(
        service.recommendation,
        "recommend",
        lambda symbol, risk_profile, asset_type, include_news: _recommendation(),
    )
    monkeypatch.setattr(
        service.alphavantage,
        "get_market_context",
        lambda symbol: {"quote": {"price": 521.25, "change_percent": 0.44}, "news": []},
    )


def test_chat_support_resistance_uses_prompt_symbol_and_bypasses_llm(monkeypatch) -> None:
    service = ChatService()
    _patch_common(monkeypatch, service)

    def _unexpected_llm(**kwargs: Any) -> str:
        raise AssertionError("LLM should be bypassed for support/resistance intent")

    monkeypatch.setattr(service, "_generate_llm_answer", _unexpected_llm)

    response = service.respond(
        message="Where are the key support and resistance levels for SPY?",
        symbol="AAPL",
        asset_type="stock",
        risk_profile="balanced",
        include_news=False,
        include_alpha_context=True,
    )

    assert response["symbol"] == "SPY"
    assert "Support(60d)=500.00" in response["answer"]
    assert "Resistance(60d)=530.00" in response["answer"]
    assert "SPY key levels:" in response["answer"]
    assert "intent:support_resistance" in response["workflow_steps"]
    assert "llm:bypass_support_resistance" in response["workflow_steps"]


def test_chat_resolve_symbol_uses_sidebar_when_prompt_has_no_ticker() -> None:
    service = ChatService()
    resolved = service._resolve_symbol(
        message="What is the short-term trend right now?",
        symbol="AAPL",
        asset_type="stock",
    )
    assert resolved == "AAPL"


def test_chat_risk_prompt_uses_risk_fallback_when_llm_unavailable(monkeypatch) -> None:
    service = ChatService()
    _patch_common(monkeypatch, service)
    monkeypatch.setattr(service, "_generate_llm_answer", lambda **kwargs: "")

    response = service.respond(
        message="What are the major risk factors for TSLA right now?",
        symbol="AAPL",
        asset_type="stock",
        risk_profile="balanced",
        include_news=False,
        include_alpha_context=True,
    )

    assert response["symbol"] == "TSLA"
    assert "risk review" in response["answer"].lower()
    assert "intent:risk_assessment" in response["workflow_steps"]
    assert "llm:fallback" in response["workflow_steps"]


def test_chat_fallback_answer_changes_by_horizon(monkeypatch) -> None:
    service = ChatService()
    _patch_common(monkeypatch, service)
    monkeypatch.setattr(service, "_generate_llm_answer", lambda **kwargs: "")

    short_response = service.respond(
        message="Should I buy AAPL for the next 2 weeks?",
        symbol="AAPL",
        asset_type="stock",
        risk_profile="balanced",
        include_news=False,
        include_alpha_context=False,
    )
    long_response = service.respond(
        message="Long-term outlook for AAPL for 12 months.",
        symbol="AAPL",
        asset_type="stock",
        risk_profile="balanced",
        include_news=False,
        include_alpha_context=False,
    )

    assert "short-term outlook" in short_response["answer"].lower()
    assert "long-term outlook" in long_response["answer"].lower()
    assert short_response["answer"] != long_response["answer"]

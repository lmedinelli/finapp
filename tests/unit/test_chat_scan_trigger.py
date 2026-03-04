from app.services.chat import ChatService


def test_chat_scan_trigger(monkeypatch) -> None:
    service = ChatService()

    monkeypatch.setattr(service, "_load_memory", lambda session_id: [])
    monkeypatch.setattr(service, "_save_memory", lambda session_id, role, content: None)
    monkeypatch.setattr(
        service.scanner,
        "scan",
        lambda: {
            "scan_id": "scan-1",
            "generated_at": "2026-03-03T00:00:00Z",
            "low_cap_max_usd": 2_000_000_000.0,
            "stock_opportunities": [],
            "crypto_opportunities": [],
            "ipo_watchlist": [],
            "ico_watchlist": [],
            "news_signals": [],
            "data_sources": ["yfinance", "coinmarketcap"],
            "warnings": [],
        },
    )

    response = service.respond(
        message="Please use coin market cap to scan for low cap gems and IPO/ICO ideas.",
        symbol=None,
        asset_type="stock",
        risk_profile="balanced",
    )

    assert response["symbol"] == "SCAN"
    assert response["market_scan"]["scan_id"] == "scan-1"
    assert "tool:scan_the_market" in response["workflow_steps"]
    assert "tool:coinmarketcap" in response["workflow_steps"]

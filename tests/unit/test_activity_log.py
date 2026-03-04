from uuid import uuid4

from sqlalchemy import select

from app.db.admin import SessionLocal
from app.models.admin import MarketScanLog, RecommendationLog
from app.services.activity_log import ActivityLogService


def test_log_recommendation_persists_row() -> None:
    service = ActivityLogService()
    session_id = f"session-{uuid4().hex[:10]}"
    service.log_recommendation(
        source="unit-test",
        session_id=session_id,
        request_message="Should I buy AAPL?",
        symbol="AAPL",
        asset_type="stock",
        risk_profile="balanced",
        answer_text="AAPL short-term=hold long-term=buy",
        workflow_steps=["tool:analysis_local"],
        recommendation={
            "short_term": {"action": "hold", "confidence": 0.6},
            "long_term": {"action": "buy", "confidence": 0.7},
        },
        analysis={"latest_close": 190.0},
        market_context={"source": "mock"},
    )

    with SessionLocal() as session:
        stmt = select(RecommendationLog).where(RecommendationLog.session_id == session_id)
        row = session.scalar(stmt)
        assert row is not None
        assert row.symbol == "AAPL"
        assert row.source == "unit-test"


def test_log_market_scan_persists_row() -> None:
    service = ActivityLogService()
    scan_id = f"scan-{uuid4().hex[:10]}"
    service.log_market_scan(
        trigger_source="unit-test",
        payload={
            "scan_id": scan_id,
            "low_cap_max_usd": 2_000_000_000.0,
            "stock_opportunities": [{"symbol": "SOFI"}],
            "crypto_opportunities": [{"symbol": "ARB"}],
            "ipo_watchlist": [],
            "ico_watchlist": [],
            "warnings": [],
            "data_sources": ["coinmarketcap"],
        },
    )

    with SessionLocal() as session:
        stmt = select(MarketScanLog).where(MarketScanLog.scan_id == scan_id)
        row = session.scalar(stmt)
        assert row is not None
        assert row.trigger_source == "unit-test"
        assert row.stock_count == 1

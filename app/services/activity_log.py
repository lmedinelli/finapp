from __future__ import annotations

import json
from typing import Any

from app.db.admin import SessionLocal
from app.repositories.admin_ops_repo import AdminOpsRepository


class ActivityLogService:
    def log_recommendation(
        self,
        *,
        source: str,
        session_id: str | None,
        request_message: str | None,
        symbol: str,
        asset_type: str,
        risk_profile: str,
        answer_text: str | None,
        workflow_steps: list[str] | None,
        recommendation: dict[str, Any] | None,
        analysis: dict[str, Any] | None,
        market_context: dict[str, Any] | None,
    ) -> None:
        short = recommendation.get("short_term", {}) if isinstance(recommendation, dict) else {}
        long = recommendation.get("long_term", {}) if isinstance(recommendation, dict) else {}
        with SessionLocal() as session:
            repo = AdminOpsRepository(session)
            repo.create_recommendation_log(
                source=source,
                session_id=session_id,
                request_message=request_message,
                symbol=symbol,
                asset_type=asset_type,
                risk_profile=risk_profile,
                short_action=str(short.get("action", "hold")),
                short_confidence=self._to_float(short.get("confidence")),
                long_action=str(long.get("action", "hold")),
                long_confidence=self._to_float(long.get("confidence")),
                answer_text=answer_text,
                workflow_steps=json.dumps(workflow_steps or [], ensure_ascii=True),
                recommendation_payload=self._safe_json(recommendation),
                analysis_payload=self._safe_json(analysis),
                market_context_payload=self._safe_json(market_context),
            )

    def log_market_scan(self, *, trigger_source: str, payload: dict[str, Any]) -> None:
        scan_id = str(payload.get("scan_id", "")).strip()
        if not scan_id:
            return
        stock_items = payload.get("stock_opportunities", [])
        crypto_items = payload.get("crypto_opportunities", [])
        ipo_items = payload.get("ipo_watchlist", [])
        ico_items = payload.get("ico_watchlist", [])
        warnings = payload.get("warnings", [])
        data_sources = payload.get("data_sources", [])

        try:
            with SessionLocal() as session:
                repo = AdminOpsRepository(session)
                repo.create_market_scan_log(
                    scan_id=scan_id,
                    trigger_source=trigger_source,
                    low_cap_max_usd=self._to_float(payload.get("low_cap_max_usd")),
                    stock_count=len(stock_items) if isinstance(stock_items, list) else 0,
                    crypto_count=len(crypto_items) if isinstance(crypto_items, list) else 0,
                    ipo_count=len(ipo_items) if isinstance(ipo_items, list) else 0,
                    ico_count=len(ico_items) if isinstance(ico_items, list) else 0,
                    payload=self._safe_json(payload),
                    warnings=self._safe_json(warnings),
                    data_sources=self._safe_json(data_sources),
                )
        except Exception:
            # Logging should never block recommendation workflows.
            return

    @staticmethod
    def _safe_json(value: Any) -> str | None:
        if value is None:
            return None
        try:
            return json.dumps(value, default=str, ensure_ascii=True)
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

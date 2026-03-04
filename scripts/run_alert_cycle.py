from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _bootstrap_project_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _warmup_market_data(*, max_symbols: int) -> dict[str, Any]:
    from app.db.admin import SessionLocal
    from app.repositories.admin_ops_repo import AdminOpsRepository
    from app.services.market_data import MarketDataService

    market_data = MarketDataService()
    attempted = 0
    inserted_rows = 0
    with_data = 0
    no_data = 0
    failures = 0

    with SessionLocal() as session:
        ops_repo = AdminOpsRepository(session)
        subscriptions = ops_repo.list_alert_subscriptions(active_only=True)

    unique_symbols: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for subscription, _ in subscriptions:
        key = (str(subscription.symbol).upper(), str(subscription.asset_type).lower())
        if key in seen:
            continue
        seen.add(key)
        unique_symbols.append(key)
        if len(unique_symbols) >= max(1, max_symbols):
            break

    for symbol, asset_type in unique_symbols:
        attempted += 1
        try:
            result = market_data.ingest(symbol=symbol, asset_type=asset_type)
            inserted = int(result.get("inserted", 0))
            status = str(result.get("status", ""))
            inserted_rows += max(0, inserted)
            if inserted > 0:
                with_data += 1
            elif status == "no_data":
                no_data += 1
        except Exception:
            failures += 1

    return {
        "attempted_symbols": attempted,
        "symbols_with_new_rows": with_data,
        "inserted_rows": inserted_rows,
        "symbols_no_data": no_data,
        "failures": failures,
    }


def main() -> None:
    _bootstrap_project_path()
    from app.services.alert_daemon import AlertDaemonService

    parser = argparse.ArgumentParser(description="Run one alert daemon cycle.")
    parser.add_argument(
        "--skip-warmup",
        action="store_true",
        help="Skip pre-cycle market data warmup ingest.",
    )
    parser.add_argument(
        "--warmup-limit",
        type=int,
        default=80,
        help="Maximum unique symbols to warm up before cycle (default: 80).",
    )
    args = parser.parse_args()

    service = AlertDaemonService()
    warmup: dict[str, Any] | None = None
    if not bool(args.skip_warmup):
        try:
            warmup = _warmup_market_data(max_symbols=max(1, int(args.warmup_limit)))
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            warmup = {
                "attempted_symbols": 0,
                "symbols_with_new_rows": 0,
                "inserted_rows": 0,
                "symbols_no_data": 0,
                "failures": 1,
                "error": str(exc),
            }
    result = service.run_cycle(trigger_source="api")
    if warmup is not None:
        result["warmup"] = warmup
    print(json.dumps(result, default=str, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

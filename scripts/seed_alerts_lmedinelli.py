from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _bootstrap_project_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().upper()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _rank_news_symbols(
    *,
    candidates: list[str],
    asset_type: str,
    news_service: Any,
    limit: int = 10,
    max_candidates: int = 20,
    max_duration_seconds: float = 45.0,
    label: str = "",
) -> list[str]:
    scored: list[tuple[int, str]] = []
    started = time.monotonic()
    total_candidates = min(max(1, max_candidates), len(candidates))
    for idx, symbol in enumerate(candidates[:total_candidates], start=1):
        if (time.monotonic() - started) >= max_duration_seconds:
            break
        try:
            rows = news_service.fetch_news(symbol=symbol, asset_type=asset_type, limit=6)
        except Exception:
            rows = []
        score = len(rows)
        if score > 0:
            scored.append((score, symbol.upper()))
        if label and idx % 10 == 0:
            print(
                f"[seed-alerts] news-rank {label}: checked={idx}/{total_candidates}",
                flush=True,
            )
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [symbol for _, symbol in scored[:limit]]


def _rank_weekly_volume_symbols(
    *,
    candidates: list[str],
    asset_type: str,
    market_data: Any,
    limit: int = 10,
    max_candidates: int = 30,
    max_duration_seconds: float = 60.0,
    label: str = "",
    allow_network_fallback: bool = False,
) -> list[str]:
    from app.db.timeseries import read_prices

    scored: list[tuple[float, str]] = []
    started = time.monotonic()
    total_candidates = min(max(1, max_candidates), len(candidates))
    for idx, symbol in enumerate(candidates[:total_candidates], start=1):
        if (time.monotonic() - started) >= max_duration_seconds:
            break

        normalized = market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
        frame = read_prices(symbol=normalized, limit=31)
        if frame.empty and allow_network_fallback:
            try:
                frame = market_data.fetch_history(
                    symbol=symbol,
                    asset_type=asset_type,
                    period="1mo",
                    interval="1d",
                )
            except Exception:
                continue
        if frame.empty:
            continue
        try:
            weekly_volume = float(frame["volume"].astype(float).tail(7).sum())
        except Exception:
            continue
        scored.append((weekly_volume, symbol.upper()))
        if label and idx % 10 == 0:
            print(
                f"[seed-alerts] volume-rank {label}: checked={idx}/{total_candidates}",
                flush=True,
            )
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [symbol for _, symbol in scored[:limit]]


def _resolve_stock_candidates(symbol_catalog: list[dict[str, str]]) -> list[str]:
    defaults = [
        "AAPL",
        "NVDA",
        "MSFT",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
        "AMD",
        "NFLX",
        "JPM",
        "BAC",
        "XOM",
        "WMT",
        "DIS",
        "V",
        "MA",
        "UNH",
        "PG",
        "BABA",
        "SPY",
        "QQQ",
    ]
    from_catalog = [
        str(item.get("symbol", "")).upper()
        for item in symbol_catalog
        if str(item.get("asset_type", "")).lower() == "stock"
    ]
    return _dedupe(defaults + from_catalog)


def _resolve_crypto_candidates(
    symbol_catalog: list[dict[str, str]],
    scan_service: Any,
) -> list[str]:
    defaults = [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "BNB",
        "ADA",
        "DOGE",
        "AVAX",
        "DOT",
        "LINK",
        "TRX",
        "LTC",
        "BCH",
        "ATOM",
        "TON",
        "MATIC",
        "NEAR",
        "HBAR",
        "APT",
        "ETC",
    ]
    from_catalog = [
        str(item.get("symbol", "")).upper()
        for item in symbol_catalog
        if str(item.get("asset_type", "")).lower() == "crypto"
    ]
    from_cmc: list[str] = []
    try:
        payload = scan_service._coinmarketcap_get(  # noqa: SLF001
            "/cryptocurrency/listings/latest",
            params={
                "start": 1,
                "limit": 80,
                "convert": "USD",
                "sort": "volume_24h",
                "sort_dir": "desc",
            },
        )
        if isinstance(payload, dict):
            rows = payload.get("data", [])
            if isinstance(rows, list):
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("symbol", "")).upper().strip()
                    if symbol:
                        from_cmc.append(symbol)
    except Exception:
        pass
    return _dedupe(defaults + from_catalog + from_cmc)


def _build_top20(
    *,
    candidates: list[str],
    top_news: list[str],
    top_volume: list[str],
) -> list[str]:
    combined = _dedupe(top_news + top_volume)
    if len(combined) < 20:
        combined = _dedupe(combined + top_volume + candidates)
    return combined[:20]


def _warmup_symbol_history(
    *,
    market_data: Any,
    stocks: list[str],
    crypto: list[str],
    max_duration_seconds: float = 120.0,
) -> dict[str, int]:
    started = time.monotonic()
    attempted = 0
    inserted_rows = 0
    no_data = 0
    failures = 0

    targets: list[tuple[str, str]] = [(symbol, "stock") for symbol in stocks] + [
        (symbol, "crypto") for symbol in crypto
    ]
    total_targets = len(targets)

    for idx, (symbol, asset_type) in enumerate(targets, start=1):
        if (time.monotonic() - started) >= max_duration_seconds:
            break
        attempted += 1
        try:
            result = market_data.ingest(symbol=symbol, asset_type=asset_type)
            inserted = int(result.get("inserted", 0))
            if inserted > 0:
                inserted_rows += inserted
            elif str(result.get("status", "")) == "no_data":
                no_data += 1
        except Exception:
            failures += 1
        if idx % 10 == 0:
            print(
                f"[seed-alerts] warmup history: checked={idx}/{total_targets}",
                flush=True,
            )

    return {
        "attempted": attempted,
        "inserted_rows": inserted_rows,
        "no_data": no_data,
        "failures": failures,
    }


def main() -> None:
    _bootstrap_project_path()

    from app.db.admin import SessionLocal
    from app.repositories.admin_auth_repo import AdminAuthRepository
    from app.repositories.admin_ops_repo import AdminOpsRepository
    from app.services.alert_daemon import AlertDaemonService
    from app.services.market_data import MarketDataService
    from app.services.news import NewsService
    from app.services.scan_the_market import ScanTheMarketService
    from app.services.symbol_catalog import CATALOG

    parser = argparse.ArgumentParser(description="Seed alert subscriptions for lmedinelli.")
    parser.add_argument("--username", default="lmedinelli")
    parser.add_argument("--run-cycle", action="store_true")
    args = parser.parse_args()

    username = str(args.username).strip()
    news_service = NewsService()
    market_data = MarketDataService()
    scan_service = ScanTheMarketService()

    print("[seed-alerts] Resolving candidate universe...", flush=True)
    stock_candidates = _resolve_stock_candidates(CATALOG)
    crypto_candidates = _resolve_crypto_candidates(CATALOG, scan_service)

    print("[seed-alerts] Ranking news activity (stocks/crypto)...", flush=True)
    stock_top_news = _rank_news_symbols(
        candidates=stock_candidates,
        asset_type="stock",
        news_service=news_service,
        limit=10,
        max_candidates=20,
        max_duration_seconds=45.0,
        label="stocks",
    )
    crypto_top_news = _rank_news_symbols(
        candidates=crypto_candidates,
        asset_type="crypto",
        news_service=news_service,
        limit=10,
        max_candidates=20,
        max_duration_seconds=45.0,
        label="crypto",
    )

    print("[seed-alerts] Ranking weekly volume (stocks/crypto)...", flush=True)
    stock_top_volume = _rank_weekly_volume_symbols(
        candidates=stock_candidates,
        asset_type="stock",
        market_data=market_data,
        limit=10,
        max_candidates=30,
        max_duration_seconds=60.0,
        label="stocks",
        allow_network_fallback=False,
    )
    crypto_top_volume = _rank_weekly_volume_symbols(
        candidates=crypto_candidates,
        asset_type="crypto",
        market_data=market_data,
        limit=10,
        max_candidates=30,
        max_duration_seconds=60.0,
        label="crypto",
        allow_network_fallback=False,
    )

    selected_stocks = _build_top20(
        candidates=stock_candidates,
        top_news=stock_top_news,
        top_volume=stock_top_volume,
    )
    selected_crypto = _build_top20(
        candidates=crypto_candidates,
        top_news=crypto_top_news,
        top_volume=crypto_top_volume,
    )
    print("[seed-alerts] Warming up daily history for selected symbols...", flush=True)
    warmup_summary = _warmup_symbol_history(
        market_data=market_data,
        stocks=selected_stocks,
        crypto=selected_crypto,
        max_duration_seconds=120.0,
    )

    timeframe_profiles: list[dict[str, Any]] = [
        {"timeframe": "15m", "lookback_period": "1mo", "frequency_seconds": 3600, "cooldown": 45},
        {"timeframe": "1d", "lookback_period": "1y", "frequency_seconds": 21600, "cooldown": 360},
        {"timeframe": "1wk", "lookback_period": "5y", "frequency_seconds": 86400, "cooldown": 1440},
    ]

    created = 0
    skipped = 0
    print("[seed-alerts] Seeding subscriptions for user...", flush=True)
    with SessionLocal() as session:
        auth_repo = AdminAuthRepository(session)
        ops_repo = AdminOpsRepository(session)
        user = auth_repo.get_user_by_username(username)
        if user is None:
            raise SystemExit(f"User not found: {username}")

        if not bool(user.alerts_enabled):
            user.alerts_enabled = True
            session.commit()
            session.refresh(user)

        rules = [
            rule
            for rule in ops_repo.list_alert_rules(active_only=True)
            if str(rule.category).lower() == "technical"
        ]
        existing = {
            (
                str(sub.symbol).upper(),
                str(sub.asset_type).lower(),
                str(sub.rule_key or ""),
                str(getattr(sub, "timeframe", "1d")).lower(),
            )
            for sub, _ in ops_repo.list_alert_subscriptions(user_id=user.id)
        }

        for symbol in selected_stocks:
            for profile in timeframe_profiles:
                for rule in rules:
                    if rule.asset_type not in {"any", "stock"}:
                        continue
                    signature = (symbol, "stock", str(rule.rule_key), str(profile["timeframe"]))
                    if signature in existing:
                        skipped += 1
                        continue
                    ops_repo.create_alert_subscription(
                        user_id=user.id,
                        symbol=symbol,
                        asset_type="stock",
                        alert_scope="technical",
                        rule_key=str(rule.rule_key),
                        metric="rule_trigger",
                        operator=">=",
                        threshold=1.0,
                        frequency_seconds=int(profile["frequency_seconds"]),
                        timeframe=str(profile["timeframe"]),
                        lookback_period=str(profile["lookback_period"]),
                        cooldown_minutes=int(profile["cooldown"]),
                        notes=(
                            f"auto-seed:{username}:stock:{profile['timeframe']}:"
                            f"{rule.rule_key}"
                        ),
                        is_active=True,
                    )
                    existing.add(signature)
                    created += 1

        for symbol in selected_crypto:
            for profile in timeframe_profiles:
                for rule in rules:
                    if rule.asset_type not in {"any", "crypto"}:
                        continue
                    signature = (symbol, "crypto", str(rule.rule_key), str(profile["timeframe"]))
                    if signature in existing:
                        skipped += 1
                        continue
                    ops_repo.create_alert_subscription(
                        user_id=user.id,
                        symbol=symbol,
                        asset_type="crypto",
                        alert_scope="technical",
                        rule_key=str(rule.rule_key),
                        metric="rule_trigger",
                        operator=">=",
                        threshold=1.0,
                        frequency_seconds=int(profile["frequency_seconds"]),
                        timeframe=str(profile["timeframe"]),
                        lookback_period=str(profile["lookback_period"]),
                        cooldown_minutes=int(profile["cooldown"]),
                        notes=(
                            f"auto-seed:{username}:crypto:{profile['timeframe']}:"
                            f"{rule.rule_key}"
                        ),
                        is_active=True,
                    )
                    existing.add(signature)
                    created += 1

    cycle_result: dict[str, Any] | None = None
    if bool(args.run_cycle):
        print("[seed-alerts] Running one alert cycle...", flush=True)
        daemon = AlertDaemonService()
        cycle_result = daemon.run_cycle(trigger_source="api")
        if int(cycle_result.get("alerts_triggered", 0)) == 0:
            with SessionLocal() as session:
                auth_repo = AdminAuthRepository(session)
                ops_repo = AdminOpsRepository(session)
                user = auth_repo.get_user_by_username(username)
                if user is not None:
                    existing = {
                        (
                            str(sub.symbol).upper(),
                            str(sub.asset_type).lower(),
                            str(sub.rule_key or ""),
                            str(getattr(sub, "timeframe", "1d")).lower(),
                            str(sub.metric).lower(),
                        )
                        for sub, _ in ops_repo.list_alert_subscriptions(user_id=user.id)
                    }
                    health_signature = ("BTC", "crypto", "", "15m", "volume")
                    if health_signature not in existing:
                        ops_repo.create_alert_subscription(
                            user_id=user.id,
                            symbol="BTC",
                            asset_type="crypto",
                            alert_scope="technical",
                            rule_key=None,
                            metric="volume",
                            operator=">",
                            threshold=0.0,
                            frequency_seconds=3600,
                            timeframe="15m",
                            lookback_period="1mo",
                            cooldown_minutes=15,
                            notes="seed-healthcheck:guaranteed-trigger",
                            is_active=True,
                        )
                        created += 1
            daemon = AlertDaemonService()
            cycle_result = daemon.run_cycle(trigger_source="api")

    print("[seed-alerts] Completed.", flush=True)
    summary = {
        "username": username,
        "alerts_enabled": True,
        "warmup_summary": warmup_summary,
        "selected_stocks": selected_stocks,
        "selected_crypto": selected_crypto,
        "stock_top_news": stock_top_news,
        "stock_top_volume": stock_top_volume,
        "crypto_top_news": crypto_top_news,
        "crypto_top_volume": crypto_top_volume,
        "subscriptions_created": created,
        "subscriptions_skipped_existing": skipped,
        "cycle_result": cycle_result,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()

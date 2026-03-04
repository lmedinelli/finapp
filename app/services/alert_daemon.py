from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pandas as pd

from app.core.config import get_settings
from app.db.admin import SessionLocal
from app.db.timeseries import insert_alert_analysis_snapshots, read_prices
from app.models.admin import AlertRule, AlertSubscription
from app.repositories.admin_ops_repo import AdminOpsRepository
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)

DEFAULT_ALERT_RULES: list[dict[str, Any]] = [
    {
        "rule_key": "buy_ema9_ema21_cross_with_rsi",
        "name": "BUY: EMA9 crosses above EMA21 + RSI confirmation",
        "description": (
            "Short-term bullish trigger when EMA9 crosses above EMA21, "
            "RSI14 is below 65, and MACD is above signal."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1h",
        "horizon": "short_term",
        "action": "buy",
        "severity": "high",
        "priority": 10,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_ema_9_over_21", "op": "==", "value": 1},
                    {"metric": "rsi_14", "op": "<=", "value": 65},
                    {"left": "macd", "op": ">", "right": "macd_signal"},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "sell_ema9_ema21_cross_with_rsi",
        "name": "SELL: EMA9 crosses below EMA21 + RSI confirmation",
        "description": (
            "Short-term bearish trigger when EMA9 crosses below EMA21, "
            "RSI14 above 35, and MACD below signal."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1h",
        "horizon": "short_term",
        "action": "sell",
        "severity": "high",
        "priority": 11,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_ema_9_under_21", "op": "==", "value": 1},
                    {"metric": "rsi_14", "op": ">=", "value": 35},
                    {"left": "macd", "op": "<", "right": "macd_signal"},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "buy_sma20_sma50_golden_short",
        "name": "BUY: SMA20 crosses above SMA50",
        "description": "Momentum trend change trigger for medium-short horizon.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "4h",
        "horizon": "short_term",
        "action": "buy",
        "severity": "medium",
        "priority": 20,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_sma_20_over_50", "op": "==", "value": 1},
                    {"metric": "momentum_30d", "op": ">", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "sell_sma20_sma50_death_short",
        "name": "SELL: SMA20 crosses below SMA50",
        "description": "Momentum downshift trigger for medium-short horizon.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "4h",
        "horizon": "short_term",
        "action": "sell",
        "severity": "medium",
        "priority": 21,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_sma_20_under_50", "op": "==", "value": 1},
                    {"metric": "momentum_30d", "op": "<", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "buy_macd_cross_with_volume",
        "name": "BUY: MACD cross up with volume expansion",
        "description": "Bullish MACD crossover with volume above 20-day average.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1d",
        "horizon": "short_term",
        "action": "buy",
        "severity": "medium",
        "priority": 30,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "macd_cross_up", "op": "==", "value": 1},
                    {"left": "volume", "op": ">", "right": "volume_sma_20"},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "sell_macd_cross_with_volume",
        "name": "SELL: MACD cross down with volume expansion",
        "description": "Bearish MACD crossover with volume above 20-day average.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1d",
        "horizon": "short_term",
        "action": "sell",
        "severity": "medium",
        "priority": 31,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "macd_cross_down", "op": "==", "value": 1},
                    {"left": "volume", "op": ">", "right": "volume_sma_20"},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "buy_rsi_oversold_reversion",
        "name": "BUY: RSI oversold mean reversion",
        "description": "RSI14 <= 30 with positive MACD slope for possible bounce.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1d",
        "horizon": "short_term",
        "action": "buy",
        "severity": "info",
        "priority": 40,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "rsi_14", "op": "<=", "value": 30},
                    {"metric": "macd_delta", "op": ">", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "sell_rsi_overbought_reversion",
        "name": "SELL: RSI overbought mean reversion",
        "description": "RSI14 >= 70 with negative MACD slope for possible pullback.",
        "category": "technical",
        "asset_type": "any",
        "timeframe": "1d",
        "horizon": "short_term",
        "action": "sell",
        "severity": "info",
        "priority": 41,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "rsi_14", "op": ">=", "value": 70},
                    {"metric": "macd_delta", "op": "<", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=120",
        "is_active": True,
    },
    {
        "rule_key": "buy_longterm_golden_50_200",
        "name": "BUY: Long-term SMA50/SMA200 golden cross",
        "description": "Long-term trend transition when SMA50 crosses above SMA200.",
        "category": "technical",
        "asset_type": "stock",
        "timeframe": "1d",
        "horizon": "long_term",
        "action": "buy",
        "severity": "high",
        "priority": 50,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_sma_50_over_200", "op": "==", "value": 1},
                    {"metric": "momentum_90d", "op": ">", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=260",
        "is_active": True,
    },
    {
        "rule_key": "sell_longterm_death_50_200",
        "name": "SELL: Long-term SMA50/SMA200 death cross",
        "description": "Long-term trend deterioration when SMA50 crosses below SMA200.",
        "category": "technical",
        "asset_type": "stock",
        "timeframe": "1d",
        "horizon": "long_term",
        "action": "sell",
        "severity": "high",
        "priority": 51,
        "expression_json": json.dumps(
            {
                "all": [
                    {"metric": "cross_sma_50_under_200", "op": "==", "value": 1},
                    {"metric": "momentum_90d", "op": "<", "value": 0},
                ]
            }
        ),
        "data_requirements": "daily_ohlcv_>=260",
        "is_active": True,
    },
    {
        "rule_key": "buy_bullish_rsi_divergence",
        "name": "BUY: Bullish RSI divergence",
        "description": (
            "Price forms a lower low while RSI forms a higher low, "
            "suggesting bearish momentum exhaustion."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "15m",
        "horizon": "short_term",
        "action": "buy",
        "severity": "high",
        "priority": 60,
        "expression_json": json.dumps(
            {"all": [{"metric": "bullish_divergence_rsi", "op": "==", "value": 1}]}
        ),
        "data_requirements": "ohlcv_>=80",
        "is_active": True,
    },
    {
        "rule_key": "sell_bearish_rsi_divergence",
        "name": "SELL: Bearish RSI divergence",
        "description": (
            "Price forms a higher high while RSI forms a lower high, "
            "suggesting upside momentum exhaustion."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "15m",
        "horizon": "short_term",
        "action": "sell",
        "severity": "high",
        "priority": 61,
        "expression_json": json.dumps(
            {"all": [{"metric": "bearish_divergence_rsi", "op": "==", "value": 1}]}
        ),
        "data_requirements": "ohlcv_>=80",
        "is_active": True,
    },
    {
        "rule_key": "buy_bullish_macd_divergence",
        "name": "BUY: Bullish MACD divergence",
        "description": (
            "Price forms a lower low while MACD forms a higher low, "
            "suggesting potential reversal."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "15m",
        "horizon": "short_term",
        "action": "buy",
        "severity": "high",
        "priority": 62,
        "expression_json": json.dumps(
            {"all": [{"metric": "bullish_divergence_macd", "op": "==", "value": 1}]}
        ),
        "data_requirements": "ohlcv_>=80",
        "is_active": True,
    },
    {
        "rule_key": "sell_bearish_macd_divergence",
        "name": "SELL: Bearish MACD divergence",
        "description": (
            "Price forms a higher high while MACD forms a lower high, "
            "suggesting potential downside reversal."
        ),
        "category": "technical",
        "asset_type": "any",
        "timeframe": "15m",
        "horizon": "short_term",
        "action": "sell",
        "severity": "high",
        "priority": 63,
        "expression_json": json.dumps(
            {"all": [{"metric": "bearish_divergence_macd", "op": "==", "value": 1}]}
        ),
        "data_requirements": "ohlcv_>=80",
        "is_active": True,
    },
]

DEFAULT_WATCHLIST: list[tuple[str, str]] = [
    ("AAPL", "stock"),
    ("NVDA", "stock"),
    ("SPY", "etf"),
    ("BTC-USD", "crypto"),
    ("ETH-USD", "crypto"),
]

_PERIOD_ORDER = ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
_ALERT_TIMEFRAMES = ["15m", "1h", "4h", "1d", "1wk"]


@dataclass(frozen=True)
class _DivergenceConfig:
    lookback: int
    pivot_window: int
    price_change_ratio: float
    oscillator_change_ratio: float
    min_pivot_gap: int
    max_signal_age_bars: int


class AlertDaemonService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.market_data = MarketDataService()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._instance_id = uuid4().hex[:12]
        self._bootstrap_metadata()

    def _bootstrap_metadata(self) -> None:
        with SessionLocal() as session:
            repo = AdminOpsRepository(session)
            for rule in DEFAULT_ALERT_RULES:
                repo.upsert_alert_rule(rule)
            state = repo.get_daemon_state()
            if state is None:
                repo.upsert_daemon_state(
                    is_enabled=bool(self.settings.alert_daemon_enabled),
                    is_running=False,
                    frequency_seconds=max(60, int(self.settings.alert_daemon_frequency_seconds)),
                    last_cycle_status="idle",
                )
            else:
                repo.upsert_daemon_state(
                    is_enabled=bool(self.settings.alert_daemon_enabled),
                    frequency_seconds=max(60, int(self.settings.alert_daemon_frequency_seconds)),
                )

    def cron_hint(self) -> str:
        frequency = max(60, int(self.settings.alert_daemon_frequency_seconds))
        minutes = max(1, frequency // 60)
        if frequency % 3600 == 0:
            hours = max(1, frequency // 3600)
            return f"0 */{hours} * * *"
        if frequency % 60 == 0:
            return f"*/{minutes} * * * *"
        return f"Every {frequency} seconds (process mode)"

    def start_background_loop(self) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.get_status()
        if not self.settings.alert_daemon_enabled:
            with SessionLocal() as session:
                AdminOpsRepository(session).upsert_daemon_state(
                    is_enabled=False,
                    is_running=False,
                    active_instance_id=None,
                    last_error="Alert daemon is disabled by ALERT_DAEMON_ENABLED=false.",
                    next_run_at=None,
                )
            return self.get_status()

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._background_loop,
            name="alert-daemon-loop",
            daemon=True,
        )
        self._thread.start()
        now = datetime.now(UTC)
        with SessionLocal() as session:
            AdminOpsRepository(session).upsert_daemon_state(
                is_enabled=True,
                is_running=True,
                active_instance_id=self._instance_id,
                last_started_at=now,
                last_heartbeat_at=now,
                next_run_at=now
                + timedelta(seconds=max(60, self.settings.alert_daemon_frequency_seconds)),
                last_error=None,
            )
        logger.info(
            "Alert daemon loop started with frequency=%ss",
            self.settings.alert_daemon_frequency_seconds,
        )
        return self.get_status()

    def stop_background_loop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        now = datetime.now(UTC)
        with SessionLocal() as session:
            AdminOpsRepository(session).upsert_daemon_state(
                is_running=False,
                active_instance_id=None,
                last_heartbeat_at=now,
                next_run_at=None,
            )
        logger.info("Alert daemon loop stopped.")
        return self.get_status()

    def _background_loop(self) -> None:
        frequency = max(60, int(self.settings.alert_daemon_frequency_seconds))
        while not self._stop_event.is_set():
            try:
                self.run_cycle(trigger_source="daemon")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Alert daemon cycle failed: %s", exc)
            if self._stop_event.wait(timeout=frequency):
                break

    def run_cycle(self, *, trigger_source: str = "manual") -> dict[str, Any]:
        if not self.settings.alert_daemon_enabled:
            return {
                "cycle_id": "",
                "trigger_source": trigger_source,
                "status": "disabled",
                "symbols_count": 0,
                "subscriptions_evaluated": 0,
                "rules_evaluated": 0,
                "alerts_triggered": 0,
                "analysis_rows_written": 0,
                "steps": ["Daemon disabled by configuration."],
                "error": "ALERT_DAEMON_ENABLED=false",
                "started_at": datetime.now(UTC),
                "finished_at": datetime.now(UTC),
                "next_run_at": None,
            }

        if not self._lock.acquire(blocking=False):
            return {
                "cycle_id": "",
                "trigger_source": trigger_source,
                "status": "busy",
                "symbols_count": 0,
                "subscriptions_evaluated": 0,
                "rules_evaluated": 0,
                "alerts_triggered": 0,
                "analysis_rows_written": 0,
                "steps": ["Skipped: another daemon cycle is already running."],
                "error": None,
                "started_at": datetime.now(UTC),
                "finished_at": datetime.now(UTC),
                "next_run_at": None,
            }

        started_at = datetime.now(UTC)
        cycle_id = uuid4().hex
        frequency = max(60, int(self.settings.alert_daemon_frequency_seconds))
        steps: list[str] = [f"cycle_start={started_at.isoformat()} source={trigger_source}"]

        with SessionLocal() as session:
            repo = AdminOpsRepository(session)
            repo.create_daemon_cycle(
                cycle_id=cycle_id,
                trigger_source=trigger_source,
                frequency_seconds=frequency,
                instance_id=self._instance_id,
                started_at=started_at,
            )
            repo.upsert_daemon_state(
                is_running=bool(self._thread and self._thread.is_alive()),
                active_instance_id=(
                    self._instance_id
                    if self._thread and self._thread.is_alive()
                    else None
                ),
                last_heartbeat_at=started_at,
                last_cycle_started_at=started_at,
                last_cycle_status="running",
                next_run_at=started_at + timedelta(seconds=frequency),
            )

        symbols_count = 0
        subscriptions_evaluated = 0
        rules_evaluated = 0
        alerts_triggered = 0
        analysis_rows_written = 0
        error_text: str | None = None
        cycle_status = "success"

        try:
            with SessionLocal() as session:
                repo = AdminOpsRepository(session)
                subscriptions = [
                    item[0] for item in repo.list_alert_subscriptions(active_only=True)
                ]
                rules = repo.list_alert_rules(active_only=True)
            steps.append(f"loaded_subscriptions={len(subscriptions)}")
            steps.append(f"loaded_rules={len(rules)}")

            symbol_targets = self._resolve_symbol_targets(
                subscriptions=subscriptions,
                rules=rules,
            )
            symbols_count = len(symbol_targets)
            steps.append(f"symbol_targets={symbols_count}")

            metrics_by_symbol: dict[tuple[str, str, str], dict[str, float]] = {}
            snapshot_rows: list[dict[str, Any]] = []

            for symbol, asset_type, timeframe, period in symbol_targets:
                try:
                    metrics, rows = self._analyze_symbol(
                        symbol=symbol,
                        asset_type=asset_type,
                        period=period,
                        timeframe=timeframe,
                        cycle_id=cycle_id,
                    )
                    metrics_by_symbol[(symbol, asset_type, timeframe)] = metrics
                    snapshot_rows.extend(rows)
                except Exception as exc:  # noqa: BLE001
                    steps.append(f"analyze_error:{symbol}:{timeframe}:{exc}")
                    continue

            if snapshot_rows:
                snapshot_frame = pd.DataFrame(snapshot_rows)
                analysis_rows_written = insert_alert_analysis_snapshots(snapshot_frame)
            steps.append(f"analysis_rows_written={analysis_rows_written}")

            trigger_rows: list[dict[str, Any]] = []
            now = datetime.now(UTC)

            for rule in rules:
                for (symbol, asset_type, timeframe), metrics in metrics_by_symbol.items():
                    if rule.asset_type not in {"any", asset_type}:
                        continue
                    if self._normalize_timeframe(rule.timeframe) != timeframe:
                        continue
                    rules_evaluated += 1
                    matched, evidence = self._evaluate_rule(rule=rule, metrics=metrics)
                    if not matched:
                        continue
                    trigger_rows.append(
                        {
                            "subscription_id": None,
                            "rule_key": rule.rule_key,
                            "rule_name": rule.name,
                            "symbol": symbol,
                            "asset_type": asset_type,
                            "timeframe": timeframe,
                            "action": rule.action,
                            "severity": rule.severity,
                            "title": f"{rule.action.upper()} signal [{rule.rule_key}]",
                            "message": evidence,
                            "metric_value": None,
                            "operator": None,
                            "threshold": None,
                            "payload": json.dumps({"evidence": evidence}, ensure_ascii=True),
                            "deliver_to_user_id": None,
                            "triggered_at": now,
                        }
                    )

            rules_by_key = {item.rule_key: item for item in rules}
            for subscription in subscriptions:
                rule_match = (
                    rules_by_key.get(subscription.rule_key) if subscription.rule_key else None
                )
                timeframe = self._normalize_timeframe(
                    subscription.timeframe if getattr(subscription, "timeframe", None) else None
                )
                if rule_match is not None and not getattr(subscription, "timeframe", None):
                    timeframe = self._normalize_timeframe(rule_match.timeframe)
                key = (
                    subscription.symbol.upper(),
                    subscription.asset_type.lower(),
                    timeframe,
                )
                metrics_opt = metrics_by_symbol.get(key)
                if metrics_opt is None:
                    continue
                metrics = metrics_opt
                subscriptions_evaluated += 1

                if self._skip_by_frequency(subscription=subscription, now=now):
                    continue

                matched = False
                evidence = ""
                metric_value: float | None = None

                if subscription.rule_key:
                    if rule_match is not None:
                        matched, evidence = self._evaluate_rule(
                            rule=rule_match,
                            metrics=metrics,
                        )
                else:
                    matched, evidence, metric_value = self._evaluate_subscription_threshold(
                        subscription=subscription,
                        metrics=metrics,
                    )

                with SessionLocal() as update_session:
                    update_repo = AdminOpsRepository(update_session)
                    target = update_repo.get_alert_subscription(subscription.id)
                    if target is not None:
                        update_repo.touch_alert_subscription(
                            subscription=target,
                            checked_at=now,
                            triggered_at=now if matched else None,
                        )

                if not matched:
                    continue
                if self._skip_by_cooldown(subscription=subscription, now=now):
                    continue

                action = "watch"
                severity = "info"
                rule_name = f"custom:{subscription.metric}"
                rule_key = subscription.rule_key or f"custom_{subscription.metric}"
                if subscription.rule_key and rule_key in rules_by_key:
                    source_rule = rules_by_key[rule_key]
                    action = source_rule.action
                    severity = source_rule.severity
                    rule_name = source_rule.name
                trigger_rows.append(
                    {
                        "subscription_id": subscription.id,
                        "rule_key": rule_key,
                        "rule_name": rule_name,
                        "symbol": subscription.symbol,
                        "asset_type": subscription.asset_type,
                        "timeframe": timeframe,
                        "action": action,
                        "severity": severity,
                        "title": f"Subscription trigger #{subscription.id}",
                        "message": evidence,
                        "metric_value": metric_value,
                        "operator": subscription.operator,
                        "threshold": subscription.threshold,
                        "payload": json.dumps(
                            {
                                "subscription_id": subscription.id,
                                "rule_key": rule_key,
                                "metric": subscription.metric,
                                "operator": subscription.operator,
                                "threshold": subscription.threshold,
                                "evidence": evidence,
                            },
                            ensure_ascii=True,
                        ),
                        "deliver_to_user_id": subscription.user_id,
                        "triggered_at": now,
                    }
                )

            alerts_triggered = len(trigger_rows)
            steps.append(f"alerts_triggered={alerts_triggered}")

            with SessionLocal() as session:
                repo = AdminOpsRepository(session)
                for row in trigger_rows:
                    repo.create_trigger_log(
                        cycle_id=cycle_id,
                        subscription_id=row["subscription_id"],
                        rule_key=row["rule_key"],
                        rule_name=row["rule_name"],
                        symbol=row["symbol"],
                        asset_type=row["asset_type"],
                        timeframe=row["timeframe"],
                        action=row["action"],
                        severity=row["severity"],
                        title=row["title"],
                        message=row["message"],
                        metric_value=row["metric_value"],
                        operator=row["operator"],
                        threshold=row["threshold"],
                        payload=row["payload"],
                        deliver_to_user_id=row["deliver_to_user_id"],
                    )
                summary = self._build_cycle_summary(
                    cycle_id=cycle_id,
                    symbols_count=symbols_count,
                    subscriptions_evaluated=subscriptions_evaluated,
                    rules_evaluated=rules_evaluated,
                    alerts_triggered=alerts_triggered,
                )
                if self.settings.alert_daemon_publish_chat_events:
                    repo.create_agent_event(
                        cycle_id=cycle_id,
                        event_type="cycle_summary",
                        message=summary,
                        payload={
                            "cycle_id": cycle_id,
                            "alerts_triggered": alerts_triggered,
                            "symbols_count": symbols_count,
                        },
                    )
                    for row in trigger_rows[:8]:
                        trigger_message = (
                            f"[{row['severity'].upper()}] "
                            f"{row['symbol']}({row['timeframe']}) {row['action'].upper()} "
                            f"- {row['rule_name']}: {row['message']}"
                        )
                        repo.create_agent_event(
                            cycle_id=cycle_id,
                            event_type="trigger",
                            message=trigger_message,
                            payload={
                                "cycle_id": cycle_id,
                                "symbol": row["symbol"],
                                "timeframe": row["timeframe"],
                                "action": row["action"],
                                "rule_key": row["rule_key"],
                            },
                        )
        except Exception as exc:  # noqa: BLE001
            cycle_status = "failed"
            error_text = str(exc)
            steps.append(f"cycle_error={error_text}")
            logger.exception("Alert cycle failed: %s", exc)
        finally:
            finished_at = datetime.now(UTC)
            next_run_at = finished_at + timedelta(seconds=frequency)
            with SessionLocal() as session:
                repo = AdminOpsRepository(session)
                cycle_row = repo.get_daemon_cycle(cycle_id)
                if cycle_row is not None:
                    repo.update_daemon_cycle(
                        cycle_row,
                        status=cycle_status,
                        symbols_count=symbols_count,
                        subscriptions_evaluated=subscriptions_evaluated,
                        rules_evaluated=rules_evaluated,
                        alerts_triggered=alerts_triggered,
                        analysis_rows_written=analysis_rows_written,
                        steps_log=json.dumps(steps, ensure_ascii=True),
                        error=error_text,
                        finished_at=finished_at,
                        next_run_at=next_run_at,
                    )

                state = repo.get_daemon_state()
                run_count = int(getattr(state, "run_count", 0)) + 1
                triggered_count = int(getattr(state, "triggered_count", 0)) + int(
                    alerts_triggered
                )
                analyzed_count = int(getattr(state, "analyzed_count", 0)) + int(
                    analysis_rows_written
                )
                repo.upsert_daemon_state(
                    is_enabled=bool(self.settings.alert_daemon_enabled),
                    is_running=bool(self._thread and self._thread.is_alive()),
                    active_instance_id=(
                        self._instance_id
                        if self._thread and self._thread.is_alive()
                        else None
                    ),
                    frequency_seconds=frequency,
                    last_heartbeat_at=finished_at,
                    last_cycle_started_at=started_at,
                    last_cycle_finished_at=finished_at,
                    last_cycle_status=cycle_status,
                    last_error=error_text,
                    next_run_at=next_run_at if self._thread and self._thread.is_alive() else None,
                    run_count=run_count,
                    triggered_count=triggered_count,
                    analyzed_count=analyzed_count,
                )
            self._lock.release()

        return {
            "cycle_id": cycle_id,
            "trigger_source": trigger_source,
            "status": cycle_status,
            "symbols_count": symbols_count,
            "subscriptions_evaluated": subscriptions_evaluated,
            "rules_evaluated": rules_evaluated,
            "alerts_triggered": alerts_triggered,
            "analysis_rows_written": analysis_rows_written,
            "steps": steps,
            "error": error_text,
            "started_at": started_at,
            "finished_at": datetime.now(UTC),
            "next_run_at": datetime.now(UTC) + timedelta(seconds=frequency),
        }

    def get_status(self) -> dict[str, Any]:
        checked_at = datetime.now(UTC)
        with SessionLocal() as session:
            repo = AdminOpsRepository(session)
            state = repo.get_daemon_state()
            latest_cycle = repo.list_daemon_cycles(limit=1)

        latest = latest_cycle[0] if latest_cycle else None
        steps: list[str] = []
        latest_cycle_id: str | None = None
        if latest is not None:
            latest_cycle_id = latest.cycle_id
            try:
                parsed = json.loads(latest.steps_log or "[]")
                if isinstance(parsed, list):
                    steps = [str(item) for item in parsed[-20:]]
            except ValueError:
                steps = []

        if state is None:
            return {
                "is_enabled": bool(self.settings.alert_daemon_enabled),
                "is_running": bool(self._thread and self._thread.is_alive()),
                "frequency_seconds": max(60, int(self.settings.alert_daemon_frequency_seconds)),
                "cron_hint": self.cron_hint(),
                "next_run_at": None,
                "last_started_at": None,
                "last_heartbeat_at": None,
                "last_cycle_started_at": None,
                "last_cycle_finished_at": None,
                "last_cycle_status": "idle",
                "last_error": None,
                "run_count": 0,
                "triggered_count": 0,
                "analyzed_count": 0,
                "active_instance_id": None,
                "latest_cycle_id": latest_cycle_id,
                "latest_cycle_steps": steps,
                "checked_at": checked_at,
            }

        return {
            "is_enabled": bool(state.is_enabled),
            "is_running": bool(state.is_running),
            "frequency_seconds": int(state.frequency_seconds),
            "cron_hint": self.cron_hint(),
            "next_run_at": state.next_run_at,
            "last_started_at": state.last_started_at,
            "last_heartbeat_at": state.last_heartbeat_at,
            "last_cycle_started_at": state.last_cycle_started_at,
            "last_cycle_finished_at": state.last_cycle_finished_at,
            "last_cycle_status": state.last_cycle_status,
            "last_error": state.last_error,
            "run_count": int(state.run_count),
            "triggered_count": int(state.triggered_count),
            "analyzed_count": int(state.analyzed_count),
            "active_instance_id": state.active_instance_id,
            "latest_cycle_id": latest_cycle_id,
            "latest_cycle_steps": steps,
            "checked_at": checked_at,
        }

    def list_rules(self, *, include_inactive: bool = False) -> list[AlertRule]:
        with SessionLocal() as session:
            repo = AdminOpsRepository(session)
            return repo.list_alert_rules(active_only=not include_inactive)

    def list_cycles(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = AdminOpsRepository(session).list_daemon_cycles(limit=limit)
        result: list[dict[str, Any]] = []
        for row in rows:
            steps: list[str] = []
            try:
                parsed = json.loads(row.steps_log or "[]")
                if isinstance(parsed, list):
                    steps = [str(item) for item in parsed]
            except ValueError:
                steps = []
            result.append(
                {
                    "id": row.id,
                    "cycle_id": row.cycle_id,
                    "trigger_source": row.trigger_source,
                    "status": row.status,
                    "frequency_seconds": row.frequency_seconds,
                    "symbols_count": row.symbols_count,
                    "subscriptions_evaluated": row.subscriptions_evaluated,
                    "rules_evaluated": row.rules_evaluated,
                    "alerts_triggered": row.alerts_triggered,
                    "analysis_rows_written": row.analysis_rows_written,
                    "started_at": row.started_at,
                    "finished_at": row.finished_at,
                    "next_run_at": row.next_run_at,
                    "instance_id": row.instance_id,
                    "error": row.error,
                    "steps": steps,
                }
            )
        return result

    def list_triggers(
        self,
        *,
        cycle_id: str | None = None,
        symbol: str | None = None,
        user_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = AdminOpsRepository(session).list_trigger_logs(
                cycle_id=cycle_id,
                symbol=symbol,
                deliver_to_user_id=user_id,
                limit=limit,
            )
        return [
            {
                "id": row.id,
                "cycle_id": row.cycle_id,
                "subscription_id": row.subscription_id,
                "rule_key": row.rule_key,
                "rule_name": row.rule_name,
                "symbol": row.symbol,
                "asset_type": row.asset_type,
                "timeframe": row.timeframe,
                "action": row.action,
                "severity": row.severity,
                "title": row.title,
                "message": row.message,
                "metric_value": row.metric_value,
                "operator": row.operator,
                "threshold": row.threshold,
                "deliver_to_user_id": row.deliver_to_user_id,
                "delivered": row.delivered,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def list_agent_events(self, *, after_id: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = AdminOpsRepository(session).list_agent_events(after_id=after_id, limit=limit)
        return [
            {
                "id": row.id,
                "cycle_id": row.cycle_id,
                "source": row.source,
                "event_type": row.event_type,
                "message": row.message,
                "payload": row.payload,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def list_analysis_snapshots(
        self,
        *,
        limit: int = 200,
        cycle_id: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        from app.db.timeseries import get_connection

        query = (
            "SELECT cycle_id, analyzed_at, symbol, asset_type, timeframe, "
            "metric, metric_value, source, meta_json "
            "FROM alert_analysis_snapshots "
            "WHERE 1=1 "
        )
        params: list[Any] = []
        if cycle_id:
            query += "AND cycle_id = ? "
            params.append(cycle_id)
        if symbol:
            query += "AND symbol = ? "
            params.append(symbol.upper())
        query += "ORDER BY analyzed_at DESC LIMIT ?"
        params.append(max(1, min(limit, 2000)))

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        except Exception:
            return []
        finally:
            conn.close()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "cycle_id": str(row[0]),
                    "analyzed_at": row[1],
                    "symbol": str(row[2]),
                    "asset_type": str(row[3]),
                    "timeframe": str(row[4]),
                    "metric": str(row[5]),
                    "metric_value": float(row[6]) if row[6] is not None else 0.0,
                    "source": str(row[7]),
                    "meta_json": str(row[8]) if row[8] is not None else None,
                }
            )
        return result

    def _resolve_symbol_targets(
        self,
        *,
        subscriptions: list[AlertSubscription],
        rules: list[AlertRule],
    ) -> list[tuple[str, str, str, str]]:
        period_by_key: dict[tuple[str, str, str], str] = {}

        rule_timeframes_by_asset: dict[str, set[str]] = {
            "stock": set(),
            "crypto": set(),
            "etf": set(),
        }
        for rule in rules:
            timeframe = self._normalize_timeframe(rule.timeframe)
            if rule.asset_type in {"stock", "crypto", "etf"}:
                rule_timeframes_by_asset[rule.asset_type].add(timeframe)
            else:
                for asset in rule_timeframes_by_asset:
                    rule_timeframes_by_asset[asset].add(timeframe)

        for subscription in subscriptions:
            symbol = subscription.symbol.upper()
            asset_type = subscription.asset_type.lower()
            timeframe = self._normalize_timeframe(getattr(subscription, "timeframe", None))
            period = self._coerce_period_for_timeframe(subscription.lookback_period, timeframe)
            key = (symbol, asset_type, timeframe)
            period_by_key[key] = self._max_period(period_by_key.get(key), period)

            for rule_timeframe in rule_timeframes_by_asset.get(asset_type, set()):
                rule_key = (symbol, asset_type, rule_timeframe)
                base_period = self._default_period_for_timeframe(rule_timeframe)
                period_by_key[rule_key] = self._max_period(period_by_key.get(rule_key), base_period)

        if not period_by_key:
            for symbol, asset_type in DEFAULT_WATCHLIST:
                timeframes = rule_timeframes_by_asset.get(asset_type, set()) or {"1d"}
                for timeframe in timeframes:
                    key = (symbol.upper(), asset_type, timeframe)
                    period_by_key[key] = self._default_period_for_timeframe(timeframe)

        rows = [
            (symbol, asset_type, timeframe, period)
            for (symbol, asset_type, timeframe), period in period_by_key.items()
        ]
        rows.sort(key=lambda item: (item[0], item[1], item[2]))
        return rows[: max(1, int(self.settings.alert_daemon_max_symbols_per_cycle))]

    @staticmethod
    def _normalize_timeframe(raw: str | None) -> str:
        value = str(raw or "").strip().lower()
        if value in _ALERT_TIMEFRAMES:
            return value
        return "1d"

    def _coerce_period_for_timeframe(self, raw_period: str | None, timeframe: str) -> str:
        period = self._coerce_period(raw_period)
        max_period = self._default_period_for_timeframe(timeframe)
        return self._min_period(period, max_period)

    @staticmethod
    def _default_period_for_timeframe(timeframe: str) -> str:
        if timeframe == "15m":
            return "1mo"
        if timeframe == "1h":
            return "3mo"
        if timeframe == "4h":
            return "6mo"
        if timeframe == "1wk":
            return "5y"
        return "1y"

    @staticmethod
    def _coerce_period(raw: str | None) -> str:
        value = str(raw or "").strip().lower()
        if value in _PERIOD_ORDER:
            return value
        return "6mo"

    @staticmethod
    def _max_period(current: str | None, candidate: str) -> str:
        if not current:
            return candidate
        try:
            current_idx = _PERIOD_ORDER.index(current)
        except ValueError:
            current_idx = 0
        try:
            candidate_idx = _PERIOD_ORDER.index(candidate)
        except ValueError:
            candidate_idx = 0
        return _PERIOD_ORDER[max(current_idx, candidate_idx)]

    @staticmethod
    def _min_period(current: str, cap: str) -> str:
        try:
            current_idx = _PERIOD_ORDER.index(current)
        except ValueError:
            current_idx = 0
        try:
            cap_idx = _PERIOD_ORDER.index(cap)
        except ValueError:
            cap_idx = len(_PERIOD_ORDER) - 1
        return _PERIOD_ORDER[min(current_idx, cap_idx)]

    def _analyze_symbol(
        self,
        *,
        symbol: str,
        asset_type: str,
        period: str,
        timeframe: str,
        cycle_id: str,
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        timeframe_norm = self._normalize_timeframe(timeframe)
        interval = self._interval_for_timeframe(timeframe_norm)
        requested_period = self._coerce_period_for_timeframe(period, timeframe_norm)
        normalized_symbol = self.market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
        history = self.market_data.fetch_history(
            symbol=normalized_symbol,
            asset_type=asset_type,
            period=requested_period,
            interval=interval,
        )
        if history.empty:
            history = self._load_local_history(
                symbol=normalized_symbol,
                asset_type=asset_type,
                timeframe=timeframe_norm,
                period=requested_period,
            )
        if history.empty and timeframe_norm in {"1d", "1wk"}:
            ingest_result = self.market_data.ingest(
                symbol=normalized_symbol,
                asset_type=asset_type,
            )
            if int(ingest_result.get("inserted", 0)) > 0:
                history = self._load_local_history(
                    symbol=normalized_symbol,
                    asset_type=asset_type,
                    timeframe=timeframe_norm,
                    period=requested_period,
                )
        if timeframe_norm == "4h":
            history = self._resample_ohlcv(history, rule="4h")
        if history.empty:
            raise ValueError(f"no history for {normalized_symbol}")

        history = history.sort_values("timestamp").reset_index(drop=True)
        min_bars = 35 if timeframe_norm != "1wk" else 26
        if len(history) < min_bars:
            raise ValueError(f"not enough history for {normalized_symbol}")

        close = history["close"].astype(float)
        volume = history["volume"].astype(float).fillna(0.0)

        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        ema_9 = close.ewm(span=9, adjust=False).mean()
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_21 = close.ewm(span=21, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        ema_50 = close.ewm(span=50, adjust=False).mean()
        ema_200 = close.ewm(span=200, adjust=False).mean()

        macd_series = ema_12 - ema_26
        macd_signal_series = macd_series.ewm(span=9, adjust=False).mean()

        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.rolling(14).mean()
        avg_loss = losses.rolling(14).mean()
        avg_loss_safe = avg_loss.mask(avg_loss == 0.0)
        rs = avg_gain / avg_loss_safe
        rsi = (100 - (100 / (1 + rs))).fillna(50.0)

        volatility_30d = close.pct_change().rolling(30).std().fillna(0.0)
        volume_sma_20 = volume.rolling(20).mean().fillna(0.0)

        latest_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
        momentum_30d = ((latest_close / float(close.iloc[-31])) - 1.0) if len(close) >= 31 else 0.0
        momentum_90d = ((latest_close / float(close.iloc[-91])) - 1.0) if len(close) >= 91 else 0.0

        resistance_60d = float(close.tail(60).max())
        support_60d = float(close.tail(60).min())
        prior_60 = close.tail(61).head(60) if len(close) >= 61 else close.tail(60)
        prior_res = float(prior_60.max()) if not prior_60.empty else resistance_60d
        prior_sup = float(prior_60.min()) if not prior_60.empty else support_60d

        cross_ema_9_over_21 = (
            float(ema_9.iloc[-2]) <= float(ema_21.iloc[-2])
            and float(ema_9.iloc[-1]) > float(ema_21.iloc[-1])
        )
        cross_ema_9_under_21 = (
            float(ema_9.iloc[-2]) >= float(ema_21.iloc[-2])
            and float(ema_9.iloc[-1]) < float(ema_21.iloc[-1])
        )
        cross_sma_20_over_50 = (
            float(sma_20.iloc[-2]) <= float(sma_50.iloc[-2])
            and float(sma_20.iloc[-1]) > float(sma_50.iloc[-1])
        )
        cross_sma_20_under_50 = (
            float(sma_20.iloc[-2]) >= float(sma_50.iloc[-2])
            and float(sma_20.iloc[-1]) < float(sma_50.iloc[-1])
        )
        cross_sma_50_over_200 = (
            float(sma_50.iloc[-2]) <= float(sma_200.iloc[-2])
            and float(sma_50.iloc[-1]) > float(sma_200.iloc[-1])
        )
        cross_sma_50_under_200 = (
            float(sma_50.iloc[-2]) >= float(sma_200.iloc[-2])
            and float(sma_50.iloc[-1]) < float(sma_200.iloc[-1])
        )
        macd_cross_up = (
            float(macd_series.iloc[-2]) <= float(macd_signal_series.iloc[-2])
            and float(macd_series.iloc[-1]) > float(macd_signal_series.iloc[-1])
        )
        macd_cross_down = (
            float(macd_series.iloc[-2]) >= float(macd_signal_series.iloc[-2])
            and float(macd_series.iloc[-1]) < float(macd_signal_series.iloc[-1])
        )

        divergence_cfg = self._divergence_config_for_timeframe(timeframe_norm=timeframe_norm)
        bullish_div_rsi, bearish_div_rsi = self._detect_divergence(
            price=close,
            oscillator=rsi,
            lookback=min(max(20, divergence_cfg.lookback), len(close)),
            pivot_window=divergence_cfg.pivot_window,
            price_change_ratio=divergence_cfg.price_change_ratio,
            oscillator_change_ratio=divergence_cfg.oscillator_change_ratio,
            min_pivot_gap=divergence_cfg.min_pivot_gap,
            max_signal_age_bars=divergence_cfg.max_signal_age_bars,
        )
        bullish_div_macd, bearish_div_macd = self._detect_divergence(
            price=close,
            oscillator=macd_series,
            lookback=min(max(20, divergence_cfg.lookback), len(close)),
            pivot_window=divergence_cfg.pivot_window,
            price_change_ratio=divergence_cfg.price_change_ratio,
            oscillator_change_ratio=divergence_cfg.oscillator_change_ratio,
            min_pivot_gap=divergence_cfg.min_pivot_gap,
            max_signal_age_bars=divergence_cfg.max_signal_age_bars,
        )

        metrics = {
            "latest_close": latest_close,
            "change_1d_pct": ((latest_close / prev_close) - 1.0) * 100 if prev_close else 0.0,
            "sma_20": float(sma_20.iloc[-1]),
            "sma_50": float(sma_50.iloc[-1]),
            "sma_200": float(sma_200.iloc[-1]) if not pd.isna(sma_200.iloc[-1]) else 0.0,
            "ema_9": float(ema_9.iloc[-1]),
            "ema_12": float(ema_12.iloc[-1]),
            "ema_21": float(ema_21.iloc[-1]),
            "ema_26": float(ema_26.iloc[-1]),
            "ema_50": float(ema_50.iloc[-1]),
            "ema_200": float(ema_200.iloc[-1]) if not pd.isna(ema_200.iloc[-1]) else 0.0,
            "macd": float(macd_series.iloc[-1]),
            "macd_signal": float(macd_signal_series.iloc[-1]),
            "macd_delta": float(macd_series.iloc[-1] - macd_series.iloc[-2]),
            "rsi_14": float(rsi.iloc[-1]),
            "volume": float(volume.iloc[-1]),
            "volume_sma_20": float(volume_sma_20.iloc[-1]),
            "volatility_30d": float(volatility_30d.iloc[-1]),
            "momentum_30d": float(momentum_30d),
            "momentum_90d": float(momentum_90d),
            "support_60d": support_60d,
            "resistance_60d": resistance_60d,
            "cross_ema_9_over_21": 1.0 if cross_ema_9_over_21 else 0.0,
            "cross_ema_9_under_21": 1.0 if cross_ema_9_under_21 else 0.0,
            "cross_sma_20_over_50": 1.0 if cross_sma_20_over_50 else 0.0,
            "cross_sma_20_under_50": 1.0 if cross_sma_20_under_50 else 0.0,
            "cross_sma_50_over_200": 1.0 if cross_sma_50_over_200 else 0.0,
            "cross_sma_50_under_200": 1.0 if cross_sma_50_under_200 else 0.0,
            "macd_cross_up": 1.0 if macd_cross_up else 0.0,
            "macd_cross_down": 1.0 if macd_cross_down else 0.0,
            "breakout_resistance_60d": 1.0 if latest_close > prior_res else 0.0,
            "breakdown_support_60d": 1.0 if latest_close < prior_sup else 0.0,
            "bullish_divergence_rsi": 1.0 if bullish_div_rsi else 0.0,
            "bearish_divergence_rsi": 1.0 if bearish_div_rsi else 0.0,
            "bullish_divergence_macd": 1.0 if bullish_div_macd else 0.0,
            "bearish_divergence_macd": 1.0 if bearish_div_macd else 0.0,
        }

        analyzed_at = (
            pd.to_datetime(history["timestamp"].iloc[-1])
            .to_pydatetime()
            .replace(tzinfo=UTC)
        )
        selected_metrics = [
            "latest_close",
            "change_1d_pct",
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_9",
            "ema_12",
            "ema_21",
            "ema_26",
            "ema_50",
            "ema_200",
            "macd",
            "macd_signal",
            "rsi_14",
            "volume",
            "volume_sma_20",
            "volatility_30d",
            "momentum_30d",
            "momentum_90d",
            "support_60d",
            "resistance_60d",
            "cross_ema_9_over_21",
            "cross_ema_9_under_21",
            "cross_sma_20_over_50",
            "cross_sma_20_under_50",
            "cross_sma_50_over_200",
            "cross_sma_50_under_200",
            "macd_cross_up",
            "macd_cross_down",
            "breakout_resistance_60d",
            "breakdown_support_60d",
            "bullish_divergence_rsi",
            "bearish_divergence_rsi",
            "bullish_divergence_macd",
            "bearish_divergence_macd",
        ]
        rows = [
            {
                "cycle_id": cycle_id,
                "analyzed_at": analyzed_at,
                "symbol": normalized_symbol,
                "asset_type": asset_type,
                "timeframe": timeframe_norm,
                "metric": metric,
                "metric_value": float(metrics.get(metric, 0.0)),
                "source": "alert_daemon",
                "meta_json": json.dumps(
                    {"period": requested_period, "interval": interval},
                    ensure_ascii=True,
                ),
            }
            for metric in selected_metrics
        ]
        return metrics, rows

    @staticmethod
    def _interval_for_timeframe(timeframe: str) -> str:
        mapping = {
            "15m": "15m",
            "1h": "60m",
            "4h": "60m",
            "1d": "1d",
            "1wk": "1wk",
        }
        return mapping.get(timeframe, "1d")

    @staticmethod
    def _resample_ohlcv(frame: pd.DataFrame, *, rule: str) -> pd.DataFrame:
        if frame.empty:
            return frame
        working = frame.copy()
        working["timestamp"] = pd.to_datetime(working["timestamp"])
        grouped = (
            working.set_index("timestamp")
            .resample(rule)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
        )
        grouped["symbol"] = str(frame["symbol"].iloc[-1])
        grouped["asset_type"] = str(frame["asset_type"].iloc[-1])
        return grouped[
            ["symbol", "asset_type", "timestamp", "open", "high", "low", "close", "volume"]
        ]

    def _load_local_history(
        self,
        *,
        symbol: str,
        asset_type: str,
        timeframe: str,
        period: str,
    ) -> pd.DataFrame:
        timeframe_norm = self._normalize_timeframe(timeframe)
        if timeframe_norm in {"15m", "1h", "4h"}:
            return pd.DataFrame()

        limit = self._history_limit_for_period(period=period, timeframe=timeframe_norm)
        frame = read_prices(symbol=symbol, limit=limit)
        if frame.empty:
            return frame

        working = frame.copy()
        working["asset_type"] = working["asset_type"].astype(str).str.lower()
        working = working[working["asset_type"] == asset_type.lower()]
        if working.empty:
            return pd.DataFrame()

        working["timestamp"] = pd.to_datetime(working["timestamp"]).dt.tz_localize(None)
        if timeframe_norm == "1wk":
            return self._resample_ohlcv(working, rule="1W")
        return working.sort_values("timestamp").reset_index(drop=True)

    @staticmethod
    def _history_limit_for_period(*, period: str, timeframe: str) -> int:
        period_days: dict[str, int] = {
            "5d": 5,
            "1mo": 31,
            "3mo": 93,
            "6mo": 186,
            "1y": 366,
            "2y": 732,
            "5y": 1830,
        }
        base_days = period_days.get(period, 186)
        if timeframe == "1wk":
            return max(80, int((base_days / 7.0) + 52))
        return max(120, int(base_days + 60))

    def _divergence_config_for_timeframe(self, *, timeframe_norm: str) -> _DivergenceConfig:
        if timeframe_norm != "15m":
            return _DivergenceConfig(
                lookback=120,
                pivot_window=3,
                price_change_ratio=0.003,
                oscillator_change_ratio=0.003,
                min_pivot_gap=2,
                max_signal_age_bars=30,
            )

        mode = str(self.settings.alert_divergence_15m_mode or "balanced").strip().lower()
        profiles: dict[str, _DivergenceConfig] = {
            "conservative": _DivergenceConfig(
                lookback=180,
                pivot_window=5,
                price_change_ratio=0.006,
                oscillator_change_ratio=0.010,
                min_pivot_gap=5,
                max_signal_age_bars=24,
            ),
            "balanced": _DivergenceConfig(
                lookback=120,
                pivot_window=3,
                price_change_ratio=0.003,
                oscillator_change_ratio=0.005,
                min_pivot_gap=3,
                max_signal_age_bars=18,
            ),
            "aggressive": _DivergenceConfig(
                lookback=80,
                pivot_window=2,
                price_change_ratio=0.0015,
                oscillator_change_ratio=0.0025,
                min_pivot_gap=2,
                max_signal_age_bars=12,
            ),
        }
        return profiles.get(mode, profiles["balanced"])

    def _detect_divergence(
        self,
        *,
        price: pd.Series,
        oscillator: pd.Series,
        lookback: int = 120,
        pivot_window: int = 3,
        price_change_ratio: float = 0.003,
        oscillator_change_ratio: float = 0.003,
        min_pivot_gap: int = 1,
        max_signal_age_bars: int = 1000,
    ) -> tuple[bool, bool]:
        price_recent = price.tail(max(20, lookback)).reset_index(drop=True)
        osc_recent = oscillator.tail(max(20, lookback)).reset_index(drop=True)
        if len(price_recent) < (pivot_window * 2 + 6):
            return False, False

        low_points = self._pivot_points(price_recent, pivot_window=pivot_window, kind="low")
        high_points = self._pivot_points(price_recent, pivot_window=pivot_window, kind="high")
        bullish = False
        bearish = False

        if len(low_points) >= 2:
            low1_idx, low2_idx = low_points[-2], low_points[-1]
            p1 = self._safe_float(price_recent.iloc[low1_idx])
            p2 = self._safe_float(price_recent.iloc[low2_idx])
            o1 = self._safe_float(osc_recent.iloc[low1_idx])
            o2 = self._safe_float(osc_recent.iloc[low2_idx])
            if (
                (low2_idx - low1_idx) >= max(1, min_pivot_gap)
                and (len(price_recent) - 1 - low2_idx) <= max(1, max_signal_age_bars)
            ):
                price_base = max(abs(p1), 1e-9)
                osc_base = max(abs(o1), 1.0)
                price_drop = (p1 - p2) / price_base
                osc_rise = (o2 - o1) / osc_base
                bullish = (
                    price_drop >= max(0.0, price_change_ratio)
                    and osc_rise >= max(0.0, oscillator_change_ratio)
                )

        if len(high_points) >= 2:
            high1_idx, high2_idx = high_points[-2], high_points[-1]
            p1 = self._safe_float(price_recent.iloc[high1_idx])
            p2 = self._safe_float(price_recent.iloc[high2_idx])
            o1 = self._safe_float(osc_recent.iloc[high1_idx])
            o2 = self._safe_float(osc_recent.iloc[high2_idx])
            if (
                (high2_idx - high1_idx) >= max(1, min_pivot_gap)
                and (len(price_recent) - 1 - high2_idx) <= max(1, max_signal_age_bars)
            ):
                price_base = max(abs(p1), 1e-9)
                osc_base = max(abs(o1), 1.0)
                price_rise = (p2 - p1) / price_base
                osc_drop = (o1 - o2) / osc_base
                bearish = (
                    price_rise >= max(0.0, price_change_ratio)
                    and osc_drop >= max(0.0, oscillator_change_ratio)
                )

        return bullish, bearish

    @staticmethod
    def _pivot_points(series: pd.Series, *, pivot_window: int, kind: str) -> list[int]:
        points: list[int] = []
        if series.empty:
            return points
        width = max(1, pivot_window)
        for idx in range(width, len(series) - width):
            current = float(series.iloc[idx])
            window = series.iloc[idx - width : idx + width + 1].astype(float)
            if window.empty:
                continue
            if kind == "low":
                if current <= float(window.min()):
                    points.append(idx)
            elif current >= float(window.max()):
                points.append(idx)
        return points

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _evaluate_rule(self, *, rule: AlertRule, metrics: dict[str, float]) -> tuple[bool, str]:
        try:
            payload = json.loads(rule.expression_json)
        except ValueError:
            return False, f"Invalid rule expression for {rule.rule_key}"
        if not isinstance(payload, dict):
            return False, f"Invalid rule expression for {rule.rule_key}"
        all_conditions = payload.get("all", [])
        any_conditions = payload.get("any", [])
        evidence: list[str] = []

        all_match = True
        if isinstance(all_conditions, list):
            for condition in all_conditions:
                passed, detail = self._evaluate_condition(condition=condition, metrics=metrics)
                evidence.append(detail)
                if not passed:
                    all_match = False
        any_match = True
        if isinstance(any_conditions, list) and any_conditions:
            any_match = False
            for condition in any_conditions:
                passed, detail = self._evaluate_condition(condition=condition, metrics=metrics)
                evidence.append(detail)
                if passed:
                    any_match = True

        matched = all_match and any_match
        return matched, "; ".join(evidence[:6])

    def _evaluate_condition(
        self,
        *,
        condition: Any,
        metrics: dict[str, float],
    ) -> tuple[bool, str]:
        if not isinstance(condition, dict):
            return False, "invalid_condition"
        left_name = str(condition.get("left", condition.get("metric", ""))).strip()
        op = str(condition.get("op", ">=")).strip()
        if not left_name:
            return False, "missing_left_metric"
        left_value = self._safe_float(metrics.get(left_name))
        if "right" in condition:
            right_raw = condition.get("right")
            if isinstance(right_raw, str):
                right_value = self._safe_float(metrics.get(right_raw))
                right_name = right_raw
            else:
                right_value = self._safe_float(right_raw)
                right_name = "right"
        else:
            right_value = self._safe_float(condition.get("value"))
            right_name = "value"

        passed = self._compare(left=left_value, op=op, right=right_value)
        detail = (
            f"{left_name}({left_value:.4f}) {op} "
            f"{right_name}({right_value:.4f}) => {'yes' if passed else 'no'}"
        )
        return passed, detail

    @staticmethod
    def _compare(*, left: float, op: str, right: float) -> bool:
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "==":
            return abs(left - right) < 1e-9
        if op == "!=":
            return abs(left - right) >= 1e-9
        return False

    def _evaluate_subscription_threshold(
        self,
        *,
        subscription: AlertSubscription,
        metrics: dict[str, float],
    ) -> tuple[bool, str, float | None]:
        metric_name = subscription.metric.strip().lower()
        value = metrics.get(metric_name)
        if value is None:
            return False, f"metric {metric_name} unavailable", None
        threshold = subscription.threshold
        if threshold is None:
            passed = value != 0.0
            return passed, f"{metric_name}={value:.4f} non-zero check", float(value)
        passed = self._compare(left=float(value), op=subscription.operator, right=float(threshold))
        return (
            passed,
            f"{metric_name}={value:.4f} {subscription.operator} {float(threshold):.4f}",
            float(value),
        )

    @staticmethod
    def _skip_by_frequency(*, subscription: AlertSubscription, now: datetime) -> bool:
        checked_at = AlertDaemonService._ensure_utc_datetime(subscription.last_checked_at)
        now_utc = AlertDaemonService._ensure_utc_datetime(now)
        if checked_at is None or now_utc is None:
            return False
        return now_utc < (checked_at + timedelta(seconds=max(60, subscription.frequency_seconds)))

    @staticmethod
    def _skip_by_cooldown(*, subscription: AlertSubscription, now: datetime) -> bool:
        triggered_at = AlertDaemonService._ensure_utc_datetime(subscription.last_triggered_at)
        now_utc = AlertDaemonService._ensure_utc_datetime(now)
        if triggered_at is None or now_utc is None:
            return False
        return now_utc < (triggered_at + timedelta(minutes=max(0, subscription.cooldown_minutes)))

    @staticmethod
    def _ensure_utc_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            parsed: datetime | None = None
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                parsed = None
            if parsed is None:
                try:
                    parsed_obj = pd.to_datetime(text, utc=True)
                    if pd.isna(parsed_obj):
                        return None
                    parsed = parsed_obj.to_pydatetime()
                except Exception:
                    return None
            if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return None

    @staticmethod
    def _build_cycle_summary(
        *,
        cycle_id: str,
        symbols_count: int,
        subscriptions_evaluated: int,
        rules_evaluated: int,
        alerts_triggered: int,
    ) -> str:
        return (
            f"[Alert Daemon] cycle={cycle_id[:10]} symbols={symbols_count}, "
            f"subscriptions={subscriptions_evaluated}, rules={rules_evaluated}, "
            f"triggers={alerts_triggered}."
        )

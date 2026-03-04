from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from app.services.alert_daemon import AlertDaemonService


def test_alert_daemon_rule_evaluator_matches_expression() -> None:
    service = AlertDaemonService()
    rule = SimpleNamespace(
        rule_key="buy_test",
        expression_json=json.dumps(
            {
                "all": [
                    {"metric": "rsi_14", "op": "<=", "value": 60},
                    {"left": "macd", "op": ">", "right": "macd_signal"},
                ]
            }
        ),
    )
    metrics = {"rsi_14": 48.2, "macd": 1.1, "macd_signal": 0.8}
    matched, evidence = service._evaluate_rule(rule=rule, metrics=metrics)  # type: ignore[arg-type]
    assert matched is True
    assert "rsi_14" in evidence


def test_alert_daemon_threshold_subscription_check() -> None:
    service = AlertDaemonService()
    subscription = SimpleNamespace(metric="rsi_14", operator="<=", threshold=35.0)
    matched, evidence, metric_value = service._evaluate_subscription_threshold(
        subscription=subscription,  # type: ignore[arg-type]
        metrics={"rsi_14": 30.5},
    )
    assert matched is True
    assert metric_value == 30.5
    assert "<=" in evidence


def test_alert_daemon_cron_hint_hourly() -> None:
    service = AlertDaemonService()
    service.settings.alert_daemon_frequency_seconds = 3600
    assert service.cron_hint() == "0 */1 * * *"


def test_alert_daemon_detects_bullish_rsi_style_divergence() -> None:
    service = AlertDaemonService()
    price = pd.Series([110, 108, 106, 107, 105, 106, 104, 105, 106, 107], dtype=float)
    oscillator = pd.Series([45, 38, 30, 33, 31, 34, 36, 38, 40, 41], dtype=float)
    bullish, bearish = service._detect_divergence(  # type: ignore[attr-defined]
        price=price,
        oscillator=oscillator,
        lookback=20,
        pivot_window=1,
    )
    assert bullish is True
    assert bearish is False


def test_alert_daemon_detects_bearish_macd_style_divergence() -> None:
    service = AlertDaemonService()
    price = pd.Series([100, 103, 106, 104, 108, 106, 110, 108, 107, 106], dtype=float)
    oscillator = pd.Series([40, 50, 70, 66, 65, 63, 60, 58, 56, 55], dtype=float)
    bullish, bearish = service._detect_divergence(  # type: ignore[attr-defined]
        price=price,
        oscillator=oscillator,
        lookback=20,
        pivot_window=1,
    )
    assert bullish is False
    assert bearish is True


def test_alert_daemon_intraday_period_is_capped_for_15m() -> None:
    service = AlertDaemonService()
    capped = service._coerce_period_for_timeframe("5y", "15m")  # type: ignore[attr-defined]
    assert capped == "1mo"


def test_alert_daemon_15m_divergence_profiles_are_ordered() -> None:
    service = AlertDaemonService()
    service.settings.alert_divergence_15m_mode = "conservative"
    conservative = service._divergence_config_for_timeframe(timeframe_norm="15m")  # type: ignore[attr-defined]
    service.settings.alert_divergence_15m_mode = "aggressive"
    aggressive = service._divergence_config_for_timeframe(timeframe_norm="15m")  # type: ignore[attr-defined]

    assert conservative.pivot_window > aggressive.pivot_window
    assert conservative.price_change_ratio > aggressive.price_change_ratio
    assert conservative.oscillator_change_ratio > aggressive.oscillator_change_ratio


def test_alert_daemon_divergence_thresholds_reduce_noise_when_strict() -> None:
    service = AlertDaemonService()
    price = pd.Series([105.0, 104.4, 104.8, 104.2, 104.6, 104.0, 104.3, 104.4], dtype=float)
    oscillator = pd.Series([35.0, 32.0, 33.5, 31.8, 33.6, 31.9, 34.0, 34.2], dtype=float)

    bullish_loose, _ = service._detect_divergence(  # type: ignore[attr-defined]
        price=price,
        oscillator=oscillator,
        lookback=20,
        pivot_window=1,
        price_change_ratio=0.0010,
        oscillator_change_ratio=0.0010,
    )
    bullish_strict, _ = service._detect_divergence(  # type: ignore[attr-defined]
        price=price,
        oscillator=oscillator,
        lookback=20,
        pivot_window=1,
        price_change_ratio=0.0080,
        oscillator_change_ratio=0.0150,
    )
    assert bullish_loose is True
    assert bullish_strict is False


def test_alert_daemon_skip_checks_handle_naive_and_aware_datetimes() -> None:
    service = AlertDaemonService()
    now_aware = datetime.now(UTC)
    naive_checked = now_aware.replace(tzinfo=None) - timedelta(minutes=10)
    naive_triggered = now_aware.replace(tzinfo=None) - timedelta(minutes=5)
    subscription = SimpleNamespace(
        last_checked_at=naive_checked,
        frequency_seconds=3600,
        last_triggered_at=naive_triggered,
        cooldown_minutes=60,
    )

    assert (
        service._skip_by_frequency(subscription=subscription, now=now_aware)  # type: ignore[arg-type]
        is True
    )
    assert (
        service._skip_by_cooldown(subscription=subscription, now=now_aware)  # type: ignore[arg-type]
        is True
    )

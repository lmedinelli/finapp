from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.services.market_data import MarketDataService


class MarketSnapshotService:
    SUPPORTED_METRICS: tuple[str, ...] = (
        "latest_close",
        "latest_open",
        "latest_high",
        "latest_low",
        "volume",
        "market_cap",
        "sma_15",
        "sma_20",
        "sma_30",
        "sma_50",
        "sma_100",
        "sma_200",
        "ema_15",
        "ema_30",
        "ema_50",
        "ema_100",
        "ema_200",
        "rsi_14",
        "rsi_30",
        "macd",
        "macd_signal",
        "momentum_10",
        "momentum_30",
        "volatility_20",
        "atr_14",
        "vwma_20",
        "bb_upper_20",
        "bb_lower_20",
        "bb_percent_b_20",
        "adx_14",
        "obv",
        "mfi_14",
        "stoch_k_14",
        "stoch_d_14",
        "cci_20",
        "williams_r_14",
        "roc_10",
    )

    def __init__(self) -> None:
        self.market_data = MarketDataService()

    def compute(
        self,
        symbol: str,
        asset_type: str,
        period: str,
        interval: str,
        metrics: list[str],
    ) -> dict[str, Any]:
        normalized_symbol = self.market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
        frame = self.market_data.fetch_history(
            symbol=normalized_symbol,
            period=period,
            interval=interval,
            asset_type=asset_type,
        )
        if frame.empty:
            raise ValueError(f"No yFinance market data available for {normalized_symbol}.")

        frame = frame.sort_values("timestamp").reset_index(drop=True)
        timestamps = pd.to_datetime(frame["timestamp"], errors="coerce")
        open_ = pd.Series(frame["open"], dtype="float64")
        high = pd.Series(frame["high"], dtype="float64")
        low = pd.Series(frame["low"], dtype="float64")
        close = pd.Series(frame["close"], dtype="float64")
        volume = pd.Series(frame["volume"], dtype="float64")

        reference = self.market_data.fetch_reference_info(
            symbol=normalized_symbol,
            asset_type=asset_type,
        )
        market_cap_series = self._compute_market_cap_series(
            close=close,
            market_cap=float(reference.get("market_cap", 0.0)),
            shares_outstanding=float(reference.get("shares_outstanding", 0.0)),
        )
        metric_series = self._build_metric_series(
            open_=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            market_cap=market_cap_series,
        )

        selected = self._normalize_requested_metrics(metrics)
        history_points = 5
        history_labels = self._build_history_labels(
            timestamps=timestamps,
            count=history_points,
            interval=interval,
        )

        selected_metrics: list[dict[str, Any]] = []
        for metric in selected:
            series = metric_series.get(metric)
            if series is None:
                series = pd.Series(dtype="float64")
            history = self._build_history(
                series=series,
                timestamps=timestamps,
                count=history_points,
                interval=interval,
            )
            value = float(history[-1]["value"]) if history else 0.0
            trend_status, trend_delta = self._trend_status(history)
            selected_metrics.append(
                {
                    "metric": metric,
                    "value": round(value, 6),
                    "history": history,
                    "trend_status": trend_status,
                    "trend_delta": round(trend_delta, 6),
                }
            )

        raw_ts = timestamps.iloc[-1]
        last_timestamp = None
        if not pd.isna(raw_ts):
            if isinstance(raw_ts, datetime):
                last_timestamp = raw_ts
            elif hasattr(raw_ts, "to_pydatetime"):
                last_timestamp = raw_ts.to_pydatetime()

        return {
            "symbol": normalized_symbol,
            "asset_type": asset_type,
            "period": period,
            "interval": interval,
            "sample_size": int(len(frame)),
            "last_timestamp": last_timestamp,
            "history_points": history_points,
            "history_labels": history_labels,
            "selected_metrics": selected_metrics,
            "available_metrics": list(self.SUPPORTED_METRICS),
        }

    def _build_metric_series(
        self,
        *,
        open_: pd.Series,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        market_cap: pd.Series,
    ) -> dict[str, pd.Series]:
        returns = close.pct_change()
        macd_line, macd_signal = self._compute_macd_series(close)
        atr_14 = self._compute_atr_series(high=high, low=low, close=close, window=14)
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2.0 * bb_std
        bb_lower = bb_mid - 2.0 * bb_std
        bb_percent_b = ((close - bb_lower) / (bb_upper - bb_lower).replace(0.0, np.nan)) * 100.0
        vwma_20 = ((close * volume).rolling(20).sum()) / (
            volume.rolling(20).sum().replace(0.0, np.nan)
        )
        obv = (np.sign(close.diff().fillna(0.0)) * volume.fillna(0.0)).cumsum()
        mfi_14 = self._compute_mfi_series(high=high, low=low, close=close, volume=volume, window=14)
        stoch_k_14, stoch_d_14 = self._compute_stochastic_series(
            high=high,
            low=low,
            close=close,
            window=14,
        )
        cci_20 = self._compute_cci_series(high=high, low=low, close=close, window=20)
        williams_r_14 = self._compute_williams_r_series(high=high, low=low, close=close, window=14)
        adx_14 = self._compute_adx_series(high=high, low=low, close=close, window=14)

        return {
            "latest_open": open_,
            "latest_high": high,
            "latest_low": low,
            "latest_close": close,
            "volume": volume,
            "market_cap": market_cap,
            "sma_15": close.rolling(15).mean(),
            "sma_20": close.rolling(20).mean(),
            "sma_30": close.rolling(30).mean(),
            "sma_50": close.rolling(50).mean(),
            "sma_100": close.rolling(100).mean(),
            "sma_200": close.rolling(200).mean(),
            "ema_15": close.ewm(span=15, adjust=False).mean(),
            "ema_30": close.ewm(span=30, adjust=False).mean(),
            "ema_50": close.ewm(span=50, adjust=False).mean(),
            "ema_100": close.ewm(span=100, adjust=False).mean(),
            "ema_200": close.ewm(span=200, adjust=False).mean(),
            "rsi_14": self._compute_rsi_series(close=close, window=14),
            "rsi_30": self._compute_rsi_series(close=close, window=30),
            "macd": macd_line,
            "macd_signal": macd_signal,
            "momentum_10": ((close / close.shift(10)) - 1.0) * 100.0,
            "momentum_30": ((close / close.shift(30)) - 1.0) * 100.0,
            "volatility_20": returns.rolling(20).std() * 100.0,
            "atr_14": atr_14,
            "vwma_20": vwma_20,
            "bb_upper_20": bb_upper,
            "bb_lower_20": bb_lower,
            "bb_percent_b_20": bb_percent_b,
            "adx_14": adx_14,
            "obv": obv,
            "mfi_14": mfi_14,
            "stoch_k_14": stoch_k_14,
            "stoch_d_14": stoch_d_14,
            "cci_20": cci_20,
            "williams_r_14": williams_r_14,
            "roc_10": ((close - close.shift(10)) / close.shift(10)) * 100.0,
        }

    @staticmethod
    def _compute_market_cap_series(
        close: pd.Series,
        market_cap: float,
        shares_outstanding: float,
    ) -> pd.Series:
        if shares_outstanding > 0.0:
            return close * shares_outstanding
        if market_cap > 0.0 and not close.empty:
            latest_close = close.iloc[-1]
            if latest_close and not pd.isna(latest_close):
                return (close / float(latest_close)) * market_cap
        return pd.Series(np.nan, index=close.index, dtype="float64")

    def _build_history(
        self,
        series: pd.Series,
        timestamps: pd.Series,
        count: int,
        interval: str,
    ) -> list[dict[str, Any]]:
        if series.empty or timestamps.empty:
            return [
                {"label": f"T-{idx}", "timestamp": None, "value": 0.0}
                for idx in range(count - 1, -1, -1)
            ]

        tail_values = series.tail(count).reset_index(drop=True)
        tail_times = timestamps.tail(count).reset_index(drop=True)
        points: list[dict[str, Any]] = []
        for raw_ts, raw_value in zip(tail_times, tail_values, strict=False):
            timestamp = None
            if not pd.isna(raw_ts):
                if isinstance(raw_ts, datetime):
                    timestamp = raw_ts
                elif hasattr(raw_ts, "to_pydatetime"):
                    timestamp = raw_ts.to_pydatetime()
            value = 0.0 if pd.isna(raw_value) else float(raw_value)
            points.append(
                {
                    "label": self._format_history_label(timestamp=timestamp, interval=interval),
                    "timestamp": timestamp,
                    "value": round(value, 6),
                }
            )

        if len(points) < count:
            missing = count - len(points)
            for idx in range(missing):
                points.insert(
                    0,
                    {
                        "label": f"T-{missing - idx}",
                        "timestamp": None,
                        "value": 0.0,
                    },
                )
        return points

    def _build_history_labels(self, timestamps: pd.Series, count: int, interval: str) -> list[str]:
        labels: list[str] = []
        for raw_ts in timestamps.tail(count):
            timestamp = None
            if not pd.isna(raw_ts):
                if isinstance(raw_ts, datetime):
                    timestamp = raw_ts
                elif hasattr(raw_ts, "to_pydatetime"):
                    timestamp = raw_ts.to_pydatetime()
            labels.append(self._format_history_label(timestamp=timestamp, interval=interval))

        while len(labels) < count:
            labels.insert(0, f"T-{count - len(labels)}")
        return labels

    @staticmethod
    def _format_history_label(timestamp: datetime | None, interval: str) -> str:
        if timestamp is None:
            return "N/A"
        lowered = interval.lower()
        if lowered.endswith("m") or lowered.endswith("h"):
            return timestamp.strftime("%m-%d %H:%M")
        if lowered.endswith("wk") or lowered.endswith("w"):
            return timestamp.strftime("%Y-%m-%d")
        return timestamp.strftime("%Y-%m-%d")

    @staticmethod
    def _trend_status(history: list[dict[str, Any]]) -> tuple[str, float]:
        if len(history) < 2:
            return "equal", 0.0
        start = float(history[0].get("value", 0.0))
        end = float(history[-1].get("value", 0.0))
        delta = end - start
        tolerance = max(abs(start) * 0.005, 1e-6)
        if delta > tolerance:
            return "improving", delta
        if delta < -tolerance:
            return "worsening", delta
        return "equal", delta

    def _normalize_requested_metrics(self, metrics: list[str]) -> list[str]:
        cleaned: list[str] = []
        for metric in metrics:
            key = metric.strip().lower()
            if key in self.SUPPORTED_METRICS and key not in cleaned:
                cleaned.append(key)
        if cleaned:
            return cleaned
        return ["latest_close", "sma_20", "sma_50", "rsi_14", "macd", "volume", "market_cap"]

    @staticmethod
    def _compute_rsi_series(close: pd.Series, window: int) -> pd.Series:
        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.ewm(alpha=1.0 / window, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1.0 / window, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def _compute_macd_series(close: pd.Series) -> tuple[pd.Series, pd.Series]:
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        return macd_line, signal

    @staticmethod
    def _compute_atr_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(alpha=1.0 / window, adjust=False).mean()

    @staticmethod
    def _compute_mfi_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        window: int,
    ) -> pd.Series:
        typical = (high + low + close) / 3.0
        raw_money_flow = typical * volume
        direction = typical.diff()
        positive_flow = raw_money_flow.where(direction > 0.0, 0.0)
        negative_flow = raw_money_flow.where(direction < 0.0, 0.0).abs()
        positive_sum = positive_flow.rolling(window).sum()
        negative_sum = negative_flow.rolling(window).sum()
        money_ratio = positive_sum / negative_sum.replace(0.0, np.nan)
        mfi = 100.0 - (100.0 / (1.0 + money_ratio))
        return mfi.fillna(50.0)

    @staticmethod
    def _compute_stochastic_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> tuple[pd.Series, pd.Series]:
        lowest_low = low.rolling(window).min()
        highest_high = high.rolling(window).max()
        denom = (highest_high - lowest_low).replace(0.0, np.nan)
        k = ((close - lowest_low) / denom) * 100.0
        d = k.rolling(3).mean()
        return k.fillna(50.0), d.fillna(50.0)

    @staticmethod
    def _compute_cci_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        typical = (high + low + close) / 3.0
        sma = typical.rolling(window).mean()
        mad = typical.rolling(window).apply(
            lambda values: np.mean(np.abs(values - np.mean(values))),
            raw=True,
        )
        cci = (typical - sma) / (0.015 * mad.replace(0.0, np.nan))
        return cci.fillna(0.0)

    @staticmethod
    def _compute_williams_r_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        highest_high = high.rolling(window).max()
        lowest_low = low.rolling(window).min()
        denom = (highest_high - lowest_low).replace(0.0, np.nan)
        williams_r = ((highest_high - close) / denom) * -100.0
        return williams_r.fillna(-50.0)

    @staticmethod
    def _compute_adx_series(
        *,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)

        atr = MarketSnapshotService._compute_atr_series(
            high=high,
            low=low,
            close=close,
            window=window,
        )
        plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / window, adjust=False).mean() / atr.replace(
            0.0, np.nan
        )
        minus_di = (
            100.0 * minus_dm.ewm(alpha=1.0 / window, adjust=False).mean() / atr.replace(0.0, np.nan)
        )
        dx = (100.0 * (plus_di - minus_di).abs()) / (plus_di + minus_di).replace(0.0, np.nan)
        adx = dx.ewm(alpha=1.0 / window, adjust=False).mean()
        return adx.fillna(0.0)

import math

import pandas as pd

from app.db.timeseries import read_prices


class AnalyticsService:
    @staticmethod
    def _safe_last(value: float) -> float:
        if pd.isna(value):
            return 0.0
        return float(value)

    def load_series(self, symbol: str) -> pd.DataFrame:
        return read_prices(symbol=symbol, limit=400)

    def compute(self, symbol: str) -> dict[str, float | str]:
        frame = self.load_series(symbol)
        if frame.empty or len(frame) < 60:
            raise ValueError("Not enough data for analysis. Ingest prices first.")

        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)

        latest = float(close.iloc[-1])
        sma_20 = self._safe_last(close.rolling(20).mean().iloc[-1])
        sma_50 = self._safe_last(close.rolling(50).mean().iloc[-1])
        sma_200 = self._safe_last(close.rolling(200).mean().iloc[-1])

        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_series = ema_12 - ema_26
        macd_signal_series = macd_series.ewm(span=9, adjust=False).mean()
        macd = self._safe_last(macd_series.iloc[-1])
        macd_signal = self._safe_last(macd_signal_series.iloc[-1])

        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.rolling(14).mean().iloc[-1]
        avg_loss = losses.rolling(14).mean().iloc[-1]
        if pd.isna(avg_gain) or pd.isna(avg_loss):
            rsi_14 = 50.0
        elif avg_loss == 0:
            rsi_14 = 100.0
        else:
            rs = float(avg_gain / avg_loss)
            rsi_14 = float(100 - (100 / (1 + rs)))

        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_14 = self._safe_last(true_range.rolling(14).mean().iloc[-1])

        bb_basis = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bollinger_upper = self._safe_last((bb_basis + 2 * bb_std).iloc[-1])
        bollinger_lower = self._safe_last((bb_basis - 2 * bb_std).iloc[-1])

        returns = close.pct_change().dropna()
        volatility = float(returns.tail(30).std() * math.sqrt(252)) if len(returns) >= 30 else 0.0
        momentum = float((latest / close.iloc[-30]) - 1.0)
        momentum_90d = float((latest / close.iloc[-90]) - 1.0) if len(close) >= 90 else 0.0

        signal_short_term = "neutral"
        if latest > sma_20 and macd > macd_signal and 45 <= rsi_14 <= 70:
            signal_short_term = "bullish"
        elif latest < sma_20 and macd < macd_signal and rsi_14 < 45:
            signal_short_term = "bearish"

        signal_long_term = "neutral"
        if len(close) >= 200:
            if latest > sma_50 > sma_200 and momentum_90d > 0:
                signal_long_term = "bullish"
            elif latest < sma_50 < sma_200 and momentum_90d < 0:
                signal_long_term = "bearish"

        trend_strength = abs((sma_20 - sma_50) / latest) if latest else 0.0
        support_60d = float(close.tail(60).min())
        resistance_60d = float(close.tail(60).max())

        return {
            "symbol": symbol.upper(),
            "latest_close": round(latest, 4),
            "sma_20": round(sma_20, 4),
            "sma_50": round(sma_50, 4),
            "sma_200": round(sma_200, 4),
            "volatility_30d": round(volatility, 4),
            "momentum_30d": round(momentum, 4),
            "momentum_90d": round(momentum_90d, 4),
            "rsi_14": round(rsi_14, 2),
            "macd": round(macd, 4),
            "macd_signal": round(macd_signal, 4),
            "atr_14": round(atr_14, 4),
            "bollinger_upper": round(bollinger_upper, 4),
            "bollinger_lower": round(bollinger_lower, 4),
            "support_60d": round(support_60d, 4),
            "resistance_60d": round(resistance_60d, 4),
            "trend_strength": round(trend_strength, 4),
            "signal_short_term": signal_short_term,
            "signal_long_term": signal_long_term,
            "signal": signal_short_term,
        }

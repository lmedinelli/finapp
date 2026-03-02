import math

import pandas as pd

from app.db.timeseries import read_prices


class AnalyticsService:
    def load_series(self, symbol: str) -> pd.DataFrame:
        return read_prices(symbol=symbol, limit=400)

    def compute(self, symbol: str) -> dict[str, float | str]:
        frame = self.load_series(symbol)
        if frame.empty or len(frame) < 50:
            raise ValueError("Not enough data for analysis. Ingest prices first.")

        close = frame["close"].astype(float)
        latest = float(close.iloc[-1])
        sma_20 = float(close.rolling(20).mean().iloc[-1])
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        returns = close.pct_change().dropna()
        volatility = float(returns.tail(30).std() * math.sqrt(252)) if len(returns) >= 30 else 0.0
        momentum = float((latest / close.iloc[-30]) - 1.0)

        signal = "neutral"
        if latest > sma_20 > sma_50 and momentum > 0:
            signal = "bullish"
        elif latest < sma_20 < sma_50 and momentum < 0:
            signal = "bearish"

        return {
            "symbol": symbol.upper(),
            "latest_close": round(latest, 4),
            "sma_20": round(sma_20, 4),
            "sma_50": round(sma_50, 4),
            "volatility_30d": round(volatility, 4),
            "momentum_30d": round(momentum, 4),
            "signal": signal,
        }

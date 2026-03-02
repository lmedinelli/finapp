from datetime import datetime

import pandas as pd
import yfinance as yf

from app.db.timeseries import ensure_schema, insert_prices


class MarketDataService:
    def __init__(self) -> None:
        ensure_schema()

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d", asset_type: str = "stock") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        frame = ticker.history(period=period, interval=interval)
        if frame.empty:
            return frame
        frame = frame.reset_index()
        frame = frame.rename(
            columns={
                "Date": "timestamp",
                "Datetime": "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None)
        frame["symbol"] = symbol.upper()
        frame["asset_type"] = asset_type
        return frame[["symbol", "asset_type", "timestamp", "open", "high", "low", "close", "volume"]]

    def ingest(self, symbol: str, asset_type: str = "stock") -> dict[str, str | int]:
        frame = self.fetch_history(symbol=symbol, asset_type=asset_type)
        inserted = insert_prices(frame)
        return {
            "symbol": symbol.upper(),
            "inserted": inserted,
            "ingested_at": datetime.utcnow().isoformat(),
        }

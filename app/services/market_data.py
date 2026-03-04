import logging
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from typing import Any, cast

import pandas as pd
import yfinance as yf

from app.db.timeseries import ensure_schema, insert_prices


class MarketDataService:
    def __init__(self) -> None:
        ensure_schema()
        # yfinance can emit verbose warning/error logs per symbol/network hiccup.
        # Keep it quiet so daemon/seed commands remain readable.
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    @staticmethod
    def normalize_symbol(symbol: str, asset_type: str) -> str:
        normalized = symbol.strip().upper()
        typo_map = {"APPL": "AAPL"}
        normalized = typo_map.get(normalized, normalized)
        if asset_type == "crypto" and "-" not in normalized:
            return f"{normalized}-USD"
        return normalized

    def fetch_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        asset_type: str = "stock",
    ) -> pd.DataFrame:
        normalized_symbol = self.normalize_symbol(symbol=symbol, asset_type=asset_type)
        ticker = yf.Ticker(normalized_symbol)
        try:
            # yfinance can print symbol-level failures directly to stdout/stderr.
            # Capture those here so daemon runs remain readable and non-blocking.
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                frame = cast(pd.DataFrame, ticker.history(period=period, interval=interval))
        except Exception:
            return pd.DataFrame()
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            return pd.DataFrame()
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
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(set(frame.columns)):
            return pd.DataFrame()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None)
        frame["symbol"] = normalized_symbol
        frame["asset_type"] = asset_type
        result = frame[
            ["symbol", "asset_type", "timestamp", "open", "high", "low", "close", "volume"]
        ]
        return cast(pd.DataFrame, result)

    def fetch_reference_info(self, symbol: str, asset_type: str = "stock") -> dict[str, float]:
        normalized_symbol = self.normalize_symbol(symbol=symbol, asset_type=asset_type)
        ticker = yf.Ticker(normalized_symbol)

        market_cap = 0.0
        shares_outstanding = 0.0

        try:
            fast_info = getattr(ticker, "fast_info", None)
            if fast_info is not None:
                market_cap = max(
                    market_cap,
                    self._to_float(
                        fast_info.get("market_cap")
                        or fast_info.get("marketCap")
                        or fast_info.get("marketcap")
                    ),
                )
                shares_outstanding = max(
                    shares_outstanding,
                    self._to_float(
                        fast_info.get("shares")
                        or fast_info.get("sharesOutstanding")
                        or fast_info.get("shares_outstanding")
                    ),
                )
        except Exception:
            pass

        if market_cap <= 0.0 or shares_outstanding <= 0.0:
            try:
                info = getattr(ticker, "info", {}) or {}
                if isinstance(info, dict):
                    market_cap = max(
                        market_cap,
                        self._to_float(info.get("marketCap") or info.get("market_cap")),
                    )
                    shares_outstanding = max(
                        shares_outstanding,
                        self._to_float(
                            info.get("sharesOutstanding")
                            or info.get("impliedSharesOutstanding")
                            or info.get("shares_outstanding")
                        ),
                    )
            except Exception:
                pass

        return {
            "market_cap": float(market_cap),
            "shares_outstanding": float(shares_outstanding),
        }

    def ingest(self, symbol: str, asset_type: str = "stock") -> dict[str, str | int]:
        normalized_symbol = self.normalize_symbol(symbol=symbol, asset_type=asset_type)
        frame = self.fetch_history(symbol=normalized_symbol, asset_type=asset_type)
        if frame.empty:
            return {
                "symbol": normalized_symbol,
                "inserted": 0,
                "status": "no_data",
                "ingested_at": datetime.now(UTC).isoformat(),
            }
        inserted = insert_prices(frame)
        return {
            "symbol": normalized_symbol,
            "inserted": inserted,
            "status": "ok",
            "ingested_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

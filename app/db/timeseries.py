from pathlib import Path

import duckdb
import pandas as pd

from app.core.config import get_settings


settings = get_settings()
Path(settings.timeseries_db_path).parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(settings.timeseries_db_path)


def ensure_schema() -> None:
    con = get_connection()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            symbol VARCHAR,
            asset_type VARCHAR,
            timestamp TIMESTAMP,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE
        )
        """
    )
    con.close()


def insert_prices(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    con = get_connection()
    con.register("incoming_prices", frame)
    con.execute(
        """
        INSERT INTO prices
        SELECT symbol, asset_type, timestamp, open, high, low, close, volume
        FROM incoming_prices
        """
    )
    inserted = frame.shape[0]
    con.close()
    return inserted


def read_prices(symbol: str, limit: int = 365) -> pd.DataFrame:
    con = get_connection()
    result = con.execute(
        """
        SELECT symbol, asset_type, timestamp, open, high, low, close, volume
        FROM prices
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        [symbol.upper(), limit],
    ).fetchdf()
    con.close()
    return result.sort_values("timestamp", ascending=True)

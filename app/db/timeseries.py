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
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prices_symbol_time
        ON prices(symbol, asset_type, timestamp)
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_analysis_snapshots (
            cycle_id VARCHAR,
            analyzed_at TIMESTAMP,
            symbol VARCHAR,
            asset_type VARCHAR,
            timeframe VARCHAR,
            metric VARCHAR,
            metric_value DOUBLE,
            source VARCHAR,
            meta_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alert_snapshots_cycle_symbol
        ON alert_analysis_snapshots(cycle_id, symbol, analyzed_at)
        """
    )
    con.close()


def insert_prices(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    con = get_connection()
    con.register("incoming_prices", frame)
    before_row = con.execute("SELECT COUNT(*) FROM prices").fetchone()
    before = int(before_row[0]) if before_row else 0
    con.execute(
        """
        INSERT INTO prices
        SELECT ip.symbol, ip.asset_type, ip.timestamp, ip.open, ip.high, ip.low, ip.close, ip.volume
        FROM incoming_prices ip
        WHERE NOT EXISTS (
            SELECT 1
            FROM prices p
            WHERE p.symbol = ip.symbol
              AND p.asset_type = ip.asset_type
              AND p.timestamp = ip.timestamp
        )
        """
    )
    after_row = con.execute("SELECT COUNT(*) FROM prices").fetchone()
    after = int(after_row[0]) if after_row else before
    con.close()
    return after - before


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


def insert_alert_analysis_snapshots(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    con = get_connection()
    try:
        con.register("incoming_alert_snapshots", frame)
        before_row = con.execute("SELECT COUNT(*) FROM alert_analysis_snapshots").fetchone()
        before = int(before_row[0]) if before_row else 0
        con.execute(
            """
            INSERT INTO alert_analysis_snapshots
            SELECT
                cycle_id,
                analyzed_at,
                symbol,
                asset_type,
                timeframe,
                metric,
                metric_value,
                source,
                meta_json
            FROM incoming_alert_snapshots
            """
        )
        after_row = con.execute("SELECT COUNT(*) FROM alert_analysis_snapshots").fetchone()
        after = int(after_row[0]) if after_row else before
        return max(0, after - before)
    finally:
        con.close()

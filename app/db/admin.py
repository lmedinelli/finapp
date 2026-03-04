import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
Path(settings.admin_db_path).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{settings.admin_db_path}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def run_admin_migrations() -> None:
    db_path = Path(settings.admin_db_path)
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    try:
        columns = _table_columns(conn=conn, table="admin_users")
        if "email" not in columns:
            conn.execute("ALTER TABLE admin_users ADD COLUMN email TEXT")
        if "role" not in columns:
            conn.execute("ALTER TABLE admin_users ADD COLUMN role TEXT DEFAULT 'admin'")
        if "subscription_ends_at" not in columns:
            conn.execute("ALTER TABLE admin_users ADD COLUMN subscription_ends_at DATETIME")
        if "alerts_enabled" not in columns:
            conn.execute("ALTER TABLE admin_users ADD COLUMN alerts_enabled INTEGER DEFAULT 0")
        if "mobile_phone" not in columns:
            conn.execute("ALTER TABLE admin_users ADD COLUMN mobile_phone TEXT")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_users_email "
            "ON admin_users(email) WHERE email IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_users_role "
            "ON admin_users(role)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_users_alerts_enabled "
            "ON admin_users(alerts_enabled)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_users_mobile_phone "
            "ON admin_users(mobile_phone)"
        )
        conn.execute("UPDATE admin_users SET role='admin' WHERE role IS NULL OR role = ''")
        conn.execute("UPDATE admin_users SET alerts_enabled=0 WHERE alerts_enabled IS NULL")

        alert_columns = _table_columns(conn=conn, table="alert_subscriptions")
        if "rule_key" not in alert_columns:
            conn.execute("ALTER TABLE alert_subscriptions ADD COLUMN rule_key TEXT")
        if "frequency_seconds" not in alert_columns:
            conn.execute(
                "ALTER TABLE alert_subscriptions "
                "ADD COLUMN frequency_seconds INTEGER DEFAULT 3600"
            )
        if "timeframe" not in alert_columns:
            conn.execute(
                "ALTER TABLE alert_subscriptions "
                "ADD COLUMN timeframe TEXT DEFAULT '1d'"
            )
        if "lookback_period" not in alert_columns:
            conn.execute(
                "ALTER TABLE alert_subscriptions "
                "ADD COLUMN lookback_period TEXT DEFAULT '6mo'"
            )
        if "cooldown_minutes" not in alert_columns:
            conn.execute(
                "ALTER TABLE alert_subscriptions "
                "ADD COLUMN cooldown_minutes INTEGER DEFAULT 60"
            )
        if "last_checked_at" not in alert_columns:
            conn.execute("ALTER TABLE alert_subscriptions ADD COLUMN last_checked_at DATETIME")
        if "last_triggered_at" not in alert_columns:
            conn.execute("ALTER TABLE alert_subscriptions ADD COLUMN last_triggered_at DATETIME")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_rule_key "
            "ON alert_subscriptions(rule_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_last_checked_at "
            "ON alert_subscriptions(last_checked_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_timeframe "
            "ON alert_subscriptions(timeframe)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_last_triggered_at "
            "ON alert_subscriptions(last_triggered_at)"
        )
        conn.execute(
            "UPDATE alert_subscriptions SET frequency_seconds=3600 "
            "WHERE frequency_seconds IS NULL OR frequency_seconds < 1"
        )
        conn.execute(
            "UPDATE alert_subscriptions SET timeframe='1d' "
            "WHERE timeframe IS NULL OR TRIM(timeframe) = ''"
        )
        conn.execute(
            "UPDATE alert_subscriptions SET lookback_period='6mo' "
            "WHERE lookback_period IS NULL OR TRIM(lookback_period) = ''"
        )
        conn.execute(
            "UPDATE alert_subscriptions SET cooldown_minutes=60 "
            "WHERE cooldown_minutes IS NULL OR cooldown_minutes < 0"
        )

        trigger_columns = _table_columns(conn=conn, table="alert_trigger_logs")
        if "timeframe" not in trigger_columns:
            conn.execute(
                "ALTER TABLE alert_trigger_logs ADD COLUMN timeframe TEXT DEFAULT '1d'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_trigger_logs_timeframe "
            "ON alert_trigger_logs(timeframe)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_trigger_logs_symbol "
            "ON alert_trigger_logs(symbol)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_trigger_logs_deliver_to_user_id "
            "ON alert_trigger_logs(deliver_to_user_id)"
        )
        conn.execute(
            "UPDATE alert_trigger_logs SET timeframe='1d' "
            "WHERE timeframe IS NULL OR TRIM(timeframe) = ''"
        )
        conn.commit()
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(item[1]) for item in rows if len(item) > 1}

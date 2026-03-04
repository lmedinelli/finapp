from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.admin import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    risk_profile: Mapped[str] = mapped_column(String(32), default="balanced")
    base_currency: Mapped[str] = mapped_column(String(8), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="stock")
    quantity: Mapped[float] = mapped_column(Float)
    avg_price: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class ChatMemory(Base):
    __tablename__ = "chat_memory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="admin", index=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    mobile_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    token: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="stock", index=True)
    alert_scope: Mapped[str] = mapped_column(String(24), default="technical")
    rule_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(80))
    operator: Mapped[str] = mapped_column(String(8), default=">=")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    timeframe: Mapped[str] = mapped_column(String(12), default="1d", index=True)
    lookback_period: Mapped[str] = mapped_column(String(24), default="6mo")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    source: Mapped[str] = mapped_column(String(32), default="chat", index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    request_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), index=True)
    risk_profile: Mapped[str] = mapped_column(String(32), default="balanced")
    short_action: Mapped[str] = mapped_column(String(16), default="hold")
    short_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    long_action: Mapped[str] = mapped_column(String(16), default="hold")
    long_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_context_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketScanLog(Base):
    __tablename__ = "market_scan_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    trigger_source: Mapped[str] = mapped_column(String(32), default="api")
    low_cap_max_usd: Mapped[float] = mapped_column(Float, default=2_000_000_000.0)
    stock_count: Mapped[int] = mapped_column(Integer, default=0)
    crypto_count: Mapped[int] = mapped_column(Integer, default=0)
    ipo_count: Mapped[int] = mapped_column(Integer, default=0)
    ico_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_sources: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(24), default="technical", index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="any", index=True)
    timeframe: Mapped[str] = mapped_column(String(24), default="1h")
    horizon: Mapped[str] = mapped_column(String(24), default="short_term")
    action: Mapped[str] = mapped_column(String(16), default="watch")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    expression_json: Mapped[str] = mapped_column(Text)
    data_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class AlertDaemonState(Base):
    __tablename__ = "alert_daemon_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    frequency_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    active_instance_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_cycle_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_cycle_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_cycle_status: Mapped[str] = mapped_column(String(24), default="idle")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    triggered_count: Mapped[int] = mapped_column(Integer, default=0)
    analyzed_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class AlertDaemonCycle(Base):
    __tablename__ = "alert_daemon_cycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    trigger_source: Mapped[str] = mapped_column(String(24), default="daemon")
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    frequency_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    symbols_count: Mapped[int] = mapped_column(Integer, default=0)
    subscriptions_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    rules_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    alerts_triggered: Mapped[int] = mapped_column(Integer, default=0)
    analysis_rows_written: Mapped[int] = mapped_column(Integer, default=0)
    steps_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    instance_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)


class AlertTriggerLog(Base):
    __tablename__ = "alert_trigger_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(64), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert_subscriptions.id"),
        nullable=True,
        index=True,
    )
    rule_key: Mapped[str] = mapped_column(String(80), index=True)
    rule_name: Mapped[str] = mapped_column(String(180))
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(12), default="1d", index=True)
    action: Mapped[str] = mapped_column(String(16), default="watch")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(240))
    message: Mapped[str] = mapped_column(Text)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(8), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliver_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id"),
        nullable=True,
        index=True,
    )
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AlertAgentEvent(Base):
    __tablename__ = "alert_agent_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="alert_daemon")
    event_type: Mapped[str] = mapped_column(String(24), default="summary", index=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

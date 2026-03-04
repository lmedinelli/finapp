from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertRuleRead(BaseModel):
    id: int
    rule_key: str
    name: str
    description: str
    category: str
    asset_type: str
    timeframe: str
    horizon: str
    action: str
    severity: str
    priority: int
    expression_json: str
    data_requirements: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AlertDaemonStatusResponse(BaseModel):
    is_enabled: bool
    is_running: bool
    frequency_seconds: int
    cron_hint: str
    next_run_at: datetime | None = None
    last_started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_cycle_status: str
    last_error: str | None = None
    run_count: int = 0
    triggered_count: int = 0
    analyzed_count: int = 0
    active_instance_id: str | None = None
    latest_cycle_id: str | None = None
    latest_cycle_steps: list[str] = []
    checked_at: datetime


class AlertDaemonRunRequest(BaseModel):
    trigger_source: Literal["manual", "api", "startup"] = "manual"


class AlertDaemonRunResponse(BaseModel):
    cycle_id: str
    trigger_source: str
    status: str
    symbols_count: int
    subscriptions_evaluated: int
    rules_evaluated: int
    alerts_triggered: int
    analysis_rows_written: int
    started_at: datetime
    finished_at: datetime
    next_run_at: datetime | None = None
    steps: list[str] = []
    error: str | None = None


class AlertDaemonCycleRead(BaseModel):
    id: int
    cycle_id: str
    trigger_source: str
    status: str
    frequency_seconds: int
    symbols_count: int
    subscriptions_evaluated: int
    rules_evaluated: int
    alerts_triggered: int
    analysis_rows_written: int
    started_at: datetime
    finished_at: datetime | None = None
    next_run_at: datetime | None = None
    instance_id: str | None = None
    error: str | None = None
    steps: list[str] = []


class AlertTriggerLogRead(BaseModel):
    id: int
    cycle_id: str
    subscription_id: int | None = None
    rule_key: str
    rule_name: str
    symbol: str
    asset_type: str
    timeframe: str
    action: str
    severity: str
    title: str
    message: str
    metric_value: float | None = None
    operator: str | None = None
    threshold: float | None = None
    deliver_to_user_id: int | None = None
    delivered: bool
    created_at: datetime


class AlertAnalysisSnapshotRead(BaseModel):
    cycle_id: str
    analyzed_at: datetime
    symbol: str
    asset_type: str
    timeframe: str
    metric: str
    metric_value: float
    source: str
    meta_json: str | None = None


class AlertAgentEventRead(BaseModel):
    id: int
    cycle_id: str | None = None
    source: str
    event_type: str
    message: str
    payload: str | None = None
    created_at: datetime


class AlertAgentFeedResponse(BaseModel):
    items: list[AlertAgentEventRead]
    next_after_id: int = Field(default=0)

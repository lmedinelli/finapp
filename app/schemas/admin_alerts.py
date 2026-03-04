from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AlertTimeframe = Literal["15m", "1h", "4h", "1d", "1wk"]


class AlertSubscriptionCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    asset_type: Literal["stock", "crypto", "etf"] = "stock"
    alert_scope: Literal["technical", "fundamental", "news", "agent"] = "technical"
    rule_key: str | None = Field(default=None, min_length=3, max_length=80)
    metric: str = Field(min_length=2, max_length=80)
    operator: Literal[">", ">=", "<", "<=", "==", "!="] = ">="
    threshold: float | None = None
    frequency_seconds: int = Field(default=3600, ge=60, le=86400)
    timeframe: AlertTimeframe = "1d"
    lookback_period: str = Field(default="6mo", min_length=2, max_length=24)
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)
    notes: str | None = Field(default=None, max_length=600)
    is_active: bool = True


class AlertSubscriptionUpdateRequest(BaseModel):
    asset_type: Literal["stock", "crypto", "etf"] | None = None
    alert_scope: Literal["technical", "fundamental", "news", "agent"] | None = None
    rule_key: str | None = Field(default=None, min_length=3, max_length=80)
    metric: str | None = Field(default=None, min_length=2, max_length=80)
    operator: Literal[">", ">=", "<", "<=", "==", "!="] | None = None
    threshold: float | None = None
    frequency_seconds: int | None = Field(default=None, ge=60, le=86400)
    timeframe: AlertTimeframe | None = None
    lookback_period: str | None = Field(default=None, min_length=2, max_length=24)
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10080)
    notes: str | None = Field(default=None, max_length=600)
    is_active: bool | None = None


class AlertSubscriptionRead(BaseModel):
    id: int
    user_id: int
    username: str
    symbol: str
    asset_type: Literal["stock", "crypto", "etf"]
    alert_scope: Literal["technical", "fundamental", "news", "agent"]
    rule_key: str | None = None
    metric: str
    operator: Literal[">", ">=", "<", "<=", "==", "!="]
    threshold: float | None = None
    frequency_seconds: int
    timeframe: AlertTimeframe
    lookback_period: str
    cooldown_minutes: int
    last_checked_at: datetime | None = None
    last_triggered_at: datetime | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

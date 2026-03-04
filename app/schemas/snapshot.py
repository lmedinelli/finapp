from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SnapshotHistoryPoint(BaseModel):
    label: str
    timestamp: datetime | None = None
    value: float


class SnapshotMetricValue(BaseModel):
    metric: str
    value: float
    history: list[SnapshotHistoryPoint] = []
    trend_status: Literal["improving", "worsening", "equal"] = "equal"
    trend_delta: float = 0.0


class MarketSnapshotResponse(BaseModel):
    symbol: str
    asset_type: Literal["stock", "crypto", "etf"]
    period: str
    interval: str
    sample_size: int
    last_timestamp: datetime | None = None
    history_points: int = 5
    history_labels: list[str] = []
    selected_metrics: list[SnapshotMetricValue]
    available_metrics: list[str]

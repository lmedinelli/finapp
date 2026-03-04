from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdminTableSummary(BaseModel):
    table: str
    rows: int


class AdminDbSummaryResponse(BaseModel):
    admin_db_path: str
    admin_db_exists: bool
    admin_tables: list[AdminTableSummary] = []
    timeseries_db_path: str
    timeseries_db_exists: bool
    timeseries_rows: int = 0
    timeseries_symbols: int = 0
    latest_price_timestamp: str | None = None
    checked_at: datetime


class AdminTestRunRequest(BaseModel):
    suite: Literal["smoke", "unit", "integration", "all"] = "smoke"


class AdminTestRunResponse(BaseModel):
    suite: Literal["smoke", "unit", "integration", "all"]
    status: Literal["passed", "failed", "timeout", "disabled", "error"]
    command: str
    duration_seconds: float
    output_tail: str
    exit_code: int | None = None
    ran_at: datetime

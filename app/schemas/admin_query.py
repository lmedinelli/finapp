from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminDbQueryRequest(BaseModel):
    target_db: Literal["admin", "timeseries"] = "timeseries"
    sql: str = Field(min_length=6, max_length=4000)
    limit: int = Field(default=200, ge=1, le=2000)


class AdminDbQueryResponse(BaseModel):
    target_db: Literal["admin", "timeseries"]
    columns: list[str]
    rows: list[list[str | float | int | bool | None]]
    row_count: int
    truncated: bool
    executed_at: datetime

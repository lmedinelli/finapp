from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdminLogsResponse(BaseModel):
    configured_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    active_level_filter: Literal["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "ALL"
    log_file_path: str
    file_exists: bool
    line_count: int
    returned_count: int
    lines: list[str] = []
    read_at: datetime

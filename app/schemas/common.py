from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    timestamp: datetime


class SystemInfoResponse(BaseModel):
    app: str
    version: str
    env: str
    author_name: str
    author_url: str
    timestamp: datetime

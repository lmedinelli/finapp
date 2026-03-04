from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class IntegrationStatusItem(BaseModel):
    key: str
    label: str
    state: Literal["up", "warn", "down"]
    detail: str


class IntegrationsStatusResponse(BaseModel):
    overall: Literal["up", "warn", "down"]
    checked_at: datetime
    integrations: list[IntegrationStatusItem]

from typing import Literal

from pydantic import BaseModel, Field


class CandleImageResponse(BaseModel):
    symbol: str
    asset_type: Literal["stock", "crypto", "etf"]
    tradingview_symbol: str
    interval: str
    theme: Literal["light", "dark"] = "dark"
    width: int = Field(ge=400, le=3840)
    height: int = Field(ge=300, le=2160)
    studies_requested: list[str] = []
    studies_applied: list[str] = []
    content_type: str
    image_base64: str
    source: str

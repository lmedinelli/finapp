from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScanTheMarketRequest(BaseModel):
    low_cap_max_usd: float = Field(default=2_000_000_000.0, gt=0.0)
    stock_limit: int = Field(default=8, ge=1, le=25)
    crypto_limit: int = Field(default=8, ge=1, le=25)
    include_ipo: bool = True
    include_ico: bool = True
    include_news: bool = True
    exchanges: list[str] | None = None


class ScanOpportunity(BaseModel):
    symbol: str
    name: str
    asset_type: Literal["stock", "crypto"]
    market_cap: float
    price: float
    change_pct: float
    volume: float
    momentum_30d: float
    score: float
    rationale: str
    source: str


class ScanHeadline(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    sentiment_label: str = "neutral"
    sentiment_score: float = 0.0
    category: Literal["stock", "crypto", "ipo", "ico", "general"] = "general"


class ScanTheMarketResponse(BaseModel):
    scan_id: str
    generated_at: datetime
    low_cap_max_usd: float
    stock_opportunities: list[ScanOpportunity] = []
    crypto_opportunities: list[ScanOpportunity] = []
    ipo_watchlist: list[ScanHeadline] = []
    ico_watchlist: list[ScanHeadline] = []
    news_signals: list[ScanHeadline] = []
    data_sources: list[str] = []
    warnings: list[str] = []

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.alphavantage import AlphaVantageContextResponse
from app.schemas.analysis import AnalysisResponse
from app.schemas.recommendation import NewsItem, RecommendationResponse
from app.schemas.scan import ScanTheMarketResponse


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=2000)
    session_id: str | None = None
    symbol: str | None = None
    asset_type: Literal["stock", "crypto", "etf"] = "stock"
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    include_news: bool = True
    include_alpha_context: bool = True
    include_merged_news_sentiment: bool = False


class ChatResponse(BaseModel):
    session_id: str | None = None
    symbol: str
    asset_type: Literal["stock", "crypto", "etf"] = "stock"
    answer: str
    inferred_horizon: Literal["short_term", "long_term", "both"]
    recommendation: RecommendationResponse | None = None
    analysis: AnalysisResponse | None = None
    news: list[NewsItem] = []
    market_context: AlphaVantageContextResponse | None = None
    market_scan: ScanTheMarketResponse | None = None
    disclaimer: str
    workflow_steps: list[str] = []

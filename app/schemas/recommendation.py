from typing import Literal

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    symbol: str
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    asset_type: Literal["stock", "crypto", "etf"] = "stock"
    include_news: bool = True


class HorizonRecommendation(BaseModel):
    action: Literal["buy", "hold", "reduce"]
    confidence: float = Field(ge=0, le=1)
    rationale: str


class NewsSentiment(BaseModel):
    score: float
    label: Literal["positive", "neutral", "negative"]
    sample_size: int
    generated_at: str


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: str


class RecommendationResponse(BaseModel):
    symbol: str
    recommendation: Literal["buy", "hold", "reduce"]
    confidence: float
    rationale: str
    short_term: HorizonRecommendation
    long_term: HorizonRecommendation
    news_sentiment: NewsSentiment
    news: list[NewsItem]
    technical_snapshot: dict[str, float | str]
    disclaimer: str

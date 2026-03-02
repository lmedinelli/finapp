from typing import Literal

from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    symbol: str
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    asset_type: Literal["stock", "crypto", "etf"] = "stock"


class RecommendationResponse(BaseModel):
    symbol: str
    recommendation: Literal["buy", "hold", "reduce"]
    confidence: float
    rationale: str

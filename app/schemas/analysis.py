from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    symbol: str
    latest_close: float
    sma_20: float
    sma_50: float
    volatility_30d: float
    momentum_30d: float
    signal: str

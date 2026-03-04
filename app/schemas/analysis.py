from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    symbol: str
    latest_close: float
    sma_20: float
    sma_50: float
    sma_200: float
    volatility_30d: float
    momentum_30d: float
    momentum_90d: float
    rsi_14: float
    macd: float
    macd_signal: float
    atr_14: float
    bollinger_upper: float
    bollinger_lower: float
    support_60d: float
    resistance_60d: float
    trend_strength: float
    signal_short_term: str
    signal_long_term: str
    signal: str

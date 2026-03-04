from pydantic import BaseModel


class AlphaVantageQuote(BaseModel):
    symbol: str
    price: float
    change_percent: float
    volume: float
    latest_trading_day: str


class AlphaVantageCandle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class AlphaVantageNewsItem(BaseModel):
    title: str
    url: str
    source: str
    time_published: str
    overall_sentiment_score: float
    overall_sentiment_label: str
    summary: str


class AlphaVantageTrend(BaseModel):
    direction: str
    change_pct_30d: float
    sma_20: float
    sma_50: float


class AlphaVantageContextResponse(BaseModel):
    symbol: str
    quote: AlphaVantageQuote | None = None
    trend: AlphaVantageTrend | None = None
    candles: list[AlphaVantageCandle] = []
    news: list[AlphaVantageNewsItem] = []
    source: str = "alphavantage-mcp"
    warnings: list[str] = []

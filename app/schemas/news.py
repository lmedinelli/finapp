from pydantic import BaseModel

from app.schemas.recommendation import NewsItem, NewsSentiment


class NewsResponse(BaseModel):
    symbol: str
    asset_type: str
    headlines: list[NewsItem]
    sentiment: NewsSentiment

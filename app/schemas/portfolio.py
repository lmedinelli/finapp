from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    user_id: int
    symbol: str = Field(min_length=1, max_length=24)
    asset_type: str = Field(default="stock", pattern="^(stock|crypto|etf)$")
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)


class PositionRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    asset_type: str
    quantity: float
    avg_price: float

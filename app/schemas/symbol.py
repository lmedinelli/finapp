from typing import Literal

from pydantic import BaseModel


class SymbolSuggestion(BaseModel):
    symbol: str
    name: str
    asset_type: Literal["stock", "crypto", "etf"]

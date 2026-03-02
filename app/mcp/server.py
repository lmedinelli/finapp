from mcp.server.fastmcp import FastMCP

from app.services.analytics import AnalyticsService
from app.services.market_data import MarketDataService

mcp = FastMCP("stocks-mcp")
market_data = MarketDataService()
analytics = AnalyticsService()


@mcp.tool()
def ingest_symbol(symbol: str, asset_type: str = "stock") -> dict:
    """Fetches latest OHLCV data and stores it in local timeseries DB."""
    return market_data.ingest(symbol=symbol, asset_type=asset_type)


@mcp.tool()
def analyze_symbol(symbol: str) -> dict:
    """Returns technical analysis metrics for a symbol."""
    return analytics.compute(symbol)


if __name__ == "__main__":
    mcp.run()

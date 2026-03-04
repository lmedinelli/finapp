from mcp.server.fastmcp import FastMCP

from app.services.alphavantage_mcp import AlphaVantageMCPService
from app.services.analytics import AnalyticsService
from app.services.chat import ChatService
from app.services.market_data import MarketDataService
from app.services.news import NewsService
from app.services.recommendation import RecommendationService
from app.services.scan_the_market import ScanTheMarketService

mcp = FastMCP("stocks-mcp")
market_data = MarketDataService()
analytics = AnalyticsService()
news_service = NewsService()
recommendation_service = RecommendationService()
chat_service = ChatService()
alphavantage_service = AlphaVantageMCPService()
scan_service = ScanTheMarketService()


@mcp.tool()
def ingest_symbol(symbol: str, asset_type: str = "stock") -> dict:
    """Fetches latest OHLCV data and stores it in local timeseries DB."""
    return market_data.ingest(symbol=symbol, asset_type=asset_type)


@mcp.tool()
def analyze_symbol(symbol: str, asset_type: str = "stock") -> dict:
    """Returns technical analysis metrics for a symbol."""
    normalized_symbol = market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
    return analytics.compute(normalized_symbol)


@mcp.tool()
def get_news(symbol: str, asset_type: str = "stock") -> dict:
    """Returns latest headlines and sentiment using SerpAPI when configured."""
    normalized_symbol = market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
    headlines = news_service.fetch_news(symbol=normalized_symbol, asset_type=asset_type)
    sentiment = news_service.sentiment_summary(headlines)
    return {
        "symbol": normalized_symbol,
        "asset_type": asset_type,
        "headlines": headlines,
        "sentiment": sentiment,
    }


@mcp.tool()
def get_recommendation(
    symbol: str,
    risk_profile: str = "balanced",
    asset_type: str = "stock",
) -> dict:
    """Returns short and long-term actions based on technical and news inputs."""
    normalized_symbol = market_data.normalize_symbol(symbol=symbol, asset_type=asset_type)
    return recommendation_service.recommend(
        symbol=normalized_symbol,
        risk_profile=risk_profile,
        asset_type=asset_type,
        include_news=True,
    )


@mcp.tool()
def chat_recommendation(
    message: str,
    symbol: str = "",
    asset_type: str = "stock",
    risk_profile: str = "balanced",
    session_id: str = "",
) -> dict:
    """Chat-oriented recommendation helper for MCP clients."""
    return chat_service.respond(
        message=message,
        symbol=symbol or None,
        asset_type=asset_type,
        risk_profile=risk_profile,
        session_id=session_id or None,
        include_news=True,
        include_alpha_context=True,
    )


@mcp.tool()
def alphavantage_market_context(symbol: str) -> dict:
    """Returns quote, daily candles, trend and sentiment news from AlphaVantage MCP."""
    return alphavantage_service.get_market_context(symbol=symbol)


@mcp.tool()
def scan_the_market(
    low_cap_max_usd: float = 2_000_000_000.0,
    stock_limit: int = 8,
    crypto_limit: int = 8,
) -> dict:
    """Scans low-cap stock and crypto opportunities with IPO/ICO/news signals."""
    return scan_service.scan(
        low_cap_max_usd=low_cap_max_usd,
        stock_limit=stock_limit,
        crypto_limit=crypto_limit,
        include_ipo=True,
        include_ico=True,
        include_news=True,
    )


if __name__ == "__main__":
    mcp.run()

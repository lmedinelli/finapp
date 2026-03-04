from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "Financial Recommender"
    app_version: str = "0.2.0"
    app_author_name: str = "Luis Medinelli"
    app_author_url: str = "https://medinelli.ai"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 8501
    admin_db_path: str = "data/admin/admin.db"
    timeseries_db_path: str = "data/timeseries/market.duckdb"
    default_currency: str = "USD"
    log_level: str = "INFO"
    log_file_path: str = "data/logs/app.log"
    serpapi_api_key: str | None = None
    serpapi_endpoint: str = "https://serpapi.com/search.json"
    news_max_items: int = 8
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    openai_base_url: str | None = None
    openai_admin_model_candidates: str = (
        "gpt-5,gpt-5-mini,gpt-5-nano,gpt-5.1,gpt-5.2,gpt-5.3-codex,"
        "gpt-4.1,gpt-4.1-mini,gpt-4o,gpt-4o-mini,o3,o4-mini"
    )
    agent_memory_messages: int = 10
    alphavantage_mcp_url: str = "https://mcp.alphavantage.co/mcp"
    alphavantage_rest_url: str = "https://www.alphavantage.co/query"
    alphavantage_api_key: str | None = None
    alphavantage_timeout_seconds: float = 20.0
    alphavantage_daily_points: int = 120
    alphavantage_news_items: int = 10
    chart_img_api_key: str | None = None
    chart_img_base_url: str = "https://api.chart-img.com"
    chart_img_timeout_seconds: float = 25.0
    chart_img_api_version: str = "v2"
    chart_img_advanced_chart_path: str = "/v2/tradingview/advanced-chart"
    chart_img_v1_advanced_chart_path: str = "/v1/tradingview/advanced-chart"
    chart_img_v2_advanced_chart_path: str = "/v2/tradingview/advanced-chart"
    chart_img_v3_advanced_chart_path: str = ""
    chart_img_max_width: int = 800
    chart_img_max_height: int = 600
    chart_img_max_studies: int = 3
    chart_img_rate_limit_per_sec: float = 1.0
    chart_img_daily_limit: int = 50
    chart_img_enforce_limits: bool = True
    chart_img_tests_enabled: bool = False
    chart_img_exchanges_path: str = "/v3/tradingview/exchange/list"
    chart_img_symbols_path: str = "/v3/tradingview/exchange/{exchange}"
    chart_img_search_path: str = "/v3/tradingview/search/{query}"
    coinmarketcap_api_key: str | None = None
    coinmarketcap_base_url: str = "https://pro-api.coinmarketcap.com/v1"
    coingecko_api_key: str | None = None
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    scan_market_low_cap_max_usd: float = 2_000_000_000.0
    scan_market_stock_limit: int = 8
    scan_market_crypto_limit: int = 8
    scan_market_news_limit: int = 10
    scan_market_exchanges: str = "NASDAQ,NYSE,AMEX"
    alert_daemon_enabled: bool = True
    alert_daemon_autostart: bool = False
    alert_daemon_frequency_seconds: int = 3600
    alert_daemon_heartbeat_grace_seconds: int = 180
    alert_daemon_max_symbols_per_cycle: int = 60
    alert_daemon_publish_chat_events: bool = True
    alert_divergence_15m_mode: str = "balanced"
    admin_enable_test_runner: bool = True
    admin_test_timeout_seconds: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

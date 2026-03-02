from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "Financial Recommender"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 8501
    admin_db_path: str = "data/admin/admin.db"
    timeseries_db_path: str = "data/timeseries/market.duckdb"
    default_currency: str = "USD"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RuntimeConfigResponse(BaseModel):
    openai_model: str
    openai_model_candidates: list[str]
    alert_divergence_15m_mode: Literal["conservative", "balanced", "aggressive"]
    chart_img_api_version: Literal["v2"]
    chart_img_v1_advanced_chart_path: str
    chart_img_v2_advanced_chart_path: str
    chart_img_v3_advanced_chart_path: str
    chart_img_timeout_seconds: float
    chart_img_max_width: int
    chart_img_max_height: int
    chart_img_max_studies: int
    chart_img_rate_limit_per_sec: float
    chart_img_daily_limit: int
    chart_img_enforce_limits: bool
    chart_img_calls_today: int
    chart_img_remaining_today: int
    chart_img_last_request_at: str | None = None
    updated_at: str | None = None


class RuntimeConfigUpdateRequest(BaseModel):
    openai_model: str | None = None
    openai_admin_model_candidates: str | None = None
    alert_divergence_15m_mode: Literal["conservative", "balanced", "aggressive"] | None = None
    chart_img_api_version: Literal["v2"] | None = None
    chart_img_v1_advanced_chart_path: str | None = None
    chart_img_v2_advanced_chart_path: str | None = None
    chart_img_v3_advanced_chart_path: str | None = None
    chart_img_timeout_seconds: float | None = None
    chart_img_max_width: int | None = None
    chart_img_max_height: int | None = None
    chart_img_max_studies: int | None = None
    chart_img_rate_limit_per_sec: float | None = None
    chart_img_daily_limit: int | None = None
    chart_img_enforce_limits: bool | None = None


class OpenAIModelCatalogResponse(BaseModel):
    configured_model: str
    models: list[str]
    available_count: int
    contains_gpt_5_3: bool
    fetched_at: datetime
    error: str | None = None


class RuntimeProbeRequest(BaseModel):
    model: str | None = None
    symbol: str = Field(default="AAPL", min_length=1, max_length=24)
    asset_type: Literal["stock", "crypto", "etf"] = "stock"
    interval: str = "1D"


class RuntimeProbeResponse(BaseModel):
    success: bool
    target: Literal["openai_model", "chart_img"]
    model: str = ""
    latency_ms: float = 0.0
    detail: str

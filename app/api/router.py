from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.admin import Base, SessionLocal, engine, get_db_session, run_admin_migrations
from app.db.timeseries import read_prices
from app.models.admin import AdminUser
from app.repositories.admin_auth_repo import AdminAuthRepository
from app.repositories.admin_ops_repo import AdminOpsRepository
from app.repositories.portfolio_repo import PortfolioRepository
from app.schemas.admin import AdminDbSummaryResponse, AdminTestRunRequest, AdminTestRunResponse
from app.schemas.admin_alerts import (
    AlertSubscriptionCreateRequest,
    AlertSubscriptionRead,
    AlertSubscriptionUpdateRequest,
)
from app.schemas.admin_auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminLogoutResponse,
    AdminUserCreateRequest,
    AdminUserRead,
    AdminUserUpdateRequest,
)
from app.schemas.admin_logs import AdminLogsResponse
from app.schemas.admin_query import AdminDbQueryRequest, AdminDbQueryResponse
from app.schemas.alert_daemon import (
    AlertAgentEventRead,
    AlertAgentFeedResponse,
    AlertAnalysisSnapshotRead,
    AlertDaemonCycleRead,
    AlertDaemonRunRequest,
    AlertDaemonRunResponse,
    AlertDaemonStatusResponse,
    AlertRuleRead,
    AlertTriggerLogRead,
)
from app.schemas.alphavantage import AlphaVantageContextResponse
from app.schemas.analysis import AnalysisResponse
from app.schemas.candle_image import CandleImageResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import HealthResponse, SystemInfoResponse
from app.schemas.integration import IntegrationsStatusResponse, IntegrationStatusItem
from app.schemas.news import NewsResponse
from app.schemas.portfolio import PositionCreate, PositionRead
from app.schemas.recommendation import (
    NewsItem,
    NewsSentiment,
    RecommendationRequest,
    RecommendationResponse,
)
from app.schemas.runtime import (
    OpenAIModelCatalogResponse,
    RuntimeConfigResponse,
    RuntimeConfigUpdateRequest,
    RuntimeProbeRequest,
    RuntimeProbeResponse,
)
from app.schemas.scan import ScanTheMarketRequest, ScanTheMarketResponse
from app.schemas.snapshot import MarketSnapshotResponse
from app.schemas.symbol import SymbolSuggestion
from app.services.activity_log import ActivityLogService
from app.services.admin_auth import AdminAuthService
from app.services.admin_tools import AdminToolsService
from app.services.alert_daemon import AlertDaemonService
from app.services.alphavantage_mcp import AlphaVantageMCPService
from app.services.analytics import AnalyticsService
from app.services.chart_img import ChartImgService
from app.services.chat import ChatService
from app.services.market_data import MarketDataService
from app.services.market_snapshot import MarketSnapshotService
from app.services.news import NewsService
from app.services.recommendation import RecommendationService
from app.services.runtime_controls import RuntimeControlsService
from app.services.scan_the_market import ScanTheMarketService
from app.services.symbol_catalog import SymbolCatalogService

Base.metadata.create_all(bind=engine)
run_admin_migrations()

router = APIRouter()
settings = get_settings()
market_data_service = MarketDataService()
analytics_service = AnalyticsService()
recommendation_service = RecommendationService()
news_service = NewsService()
chat_service = ChatService()
alphavantage_service = AlphaVantageMCPService()
symbol_catalog_service = SymbolCatalogService()
admin_tools_service = AdminToolsService()
admin_auth_service = AdminAuthService()
market_snapshot_service = MarketSnapshotService()
chart_img_service = ChartImgService()
scan_the_market_service = ScanTheMarketService()
activity_log_service = ActivityLogService()
runtime_controls_service = RuntimeControlsService()
alert_daemon_service = AlertDaemonService()
runtime_controls_service.apply_runtime_overrides()

with SessionLocal() as bootstrap_session:
    admin_auth_service.ensure_default_admin_user(bootstrap_session)


def _overall_state(states: list[str]) -> Literal["up", "warn", "down"]:
    if "down" in states:
        return "down"
    if "warn" in states:
        return "warn"
    return "up"


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _admin_user_to_schema(user: AdminUser) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        role="admin" if user.role == "admin" else "user",
        subscription_ends_at=user.subscription_ends_at,
        alerts_enabled=bool(user.alerts_enabled),
        mobile_phone=user.mobile_phone,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _subscription_is_active(user: AdminUser) -> bool:
    if user.subscription_ends_at is None:
        return False
    expiry = user.subscription_ends_at
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    now = datetime.now(UTC).replace(tzinfo=None)
    return expiry >= now


def _alert_to_schema(subscription: Any, username: str) -> AlertSubscriptionRead:
    return AlertSubscriptionRead(
        id=subscription.id,
        user_id=subscription.user_id,
        username=username,
        symbol=subscription.symbol,
        asset_type=subscription.asset_type,
        alert_scope=subscription.alert_scope,
        rule_key=subscription.rule_key,
        metric=subscription.metric,
        operator=subscription.operator,
        threshold=subscription.threshold,
        frequency_seconds=int(subscription.frequency_seconds),
        timeframe=subscription.timeframe,
        lookback_period=subscription.lookback_period,
        cooldown_minutes=int(subscription.cooldown_minutes),
        last_checked_at=subscription.last_checked_at,
        last_triggered_at=subscription.last_triggered_at,
        notes=subscription.notes,
        is_active=subscription.is_active,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


def require_admin_user(
    authorization: str | None = Header(default=None),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminUser:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid admin token.")
    user = admin_auth_service.authenticate_token(session=db, token=token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin token expired or invalid.")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role is required for this endpoint.")
    return user


def require_authenticated_user(
    authorization: str | None = Header(default=None),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminUser:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid auth token.")
    user = admin_auth_service.authenticate_token(session=db, token=token)
    if user is None:
        raise HTTPException(status_code=401, detail="Auth token expired or invalid.")
    return user


def require_admin_or_subscribed_user(
    user: AdminUser = Depends(require_authenticated_user),  # noqa: B008
) -> AdminUser:
    if user.role == "admin" or _subscription_is_active(user):
        return user
    raise HTTPException(
        status_code=403,
        detail="This section requires admin role or an active subscription.",
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, timestamp=datetime.now(UTC))


@router.get("/system/info", response_model=SystemInfoResponse)
def system_info() -> SystemInfoResponse:
    return SystemInfoResponse(
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        author_name=settings.app_author_name,
        author_url=settings.app_author_url,
        timestamp=datetime.now(UTC),
    )


@router.post("/market/ingest/{symbol}")
def ingest_symbol(symbol: str, asset_type: str = "stock") -> dict[str, str | int]:
    return market_data_service.ingest(symbol=symbol, asset_type=asset_type)


@router.get("/market/symbol-search", response_model=list[SymbolSuggestion])
def symbol_search(q: str = "", limit: int = 12) -> list[SymbolSuggestion]:
    suggestions = symbol_catalog_service.search(query=q, limit=limit)
    return [SymbolSuggestion.model_validate(item) for item in suggestions]


@router.get("/market/snapshot/{symbol}", response_model=MarketSnapshotResponse)
def market_snapshot(
    symbol: str,
    asset_type: str = "stock",
    period: str = "6mo",
    interval: str = "1d",
    metrics: str = "latest_close,sma_20,sma_50,rsi_14,macd,volume",
) -> MarketSnapshotResponse:
    metric_list = [item.strip().lower() for item in metrics.split(",") if item.strip()]
    try:
        result = market_snapshot_service.compute(
            symbol=symbol,
            asset_type=asset_type,
            period=period,
            interval=interval,
            metrics=metric_list,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MarketSnapshotResponse.model_validate(result)


@router.get("/market/candle-image/{symbol}", response_model=CandleImageResponse)
def market_candle_image(
    symbol: str,
    asset_type: str = "stock",
    interval: str = "1D",
    theme: str = "dark",
    width: int = 800,
    height: int = 600,
    studies: str = "",
    exchange: str | None = None,
) -> CandleImageResponse:
    parsed_studies = [item.strip().lower() for item in studies.split(",") if item.strip()]
    try:
        result = chart_img_service.render_candle_image(
            symbol=symbol,
            asset_type=asset_type,
            interval=interval,
            theme=theme,
            width=width,
            height=height,
            studies=parsed_studies,
            exchange=exchange,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CandleImageResponse.model_validate(result)


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def analyze_symbol(symbol: str, asset_type: str = "stock") -> AnalysisResponse:
    normalized_symbol = market_data_service.normalize_symbol(
        symbol=symbol,
        asset_type=asset_type,
    )
    try:
        result = analytics_service.compute(normalized_symbol)
        return AnalysisResponse.model_validate(result)
    except ValueError as exc:
        ingest_result = market_data_service.ingest(normalized_symbol, asset_type=asset_type)
        if ingest_result.get("inserted", 0) == 0:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No market data available for {normalized_symbol} ({asset_type}). "
                    "Check symbol or ingest data first."
                ),
            ) from exc
        try:
            result = analytics_service.compute(normalized_symbol)
            return AnalysisResponse.model_validate(result)
        except ValueError as second_exc:
            raise HTTPException(status_code=404, detail=str(second_exc)) from second_exc


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest) -> RecommendationResponse:
    try:
        normalized_symbol = market_data_service.normalize_symbol(
            symbol=payload.symbol,
            asset_type=payload.asset_type,
        )
        result = recommendation_service.recommend(
            symbol=normalized_symbol,
            risk_profile=payload.risk_profile,
            asset_type=payload.asset_type,
            include_news=payload.include_news,
        )
        activity_log_service.log_recommendation(
            source="recommendations_api",
            session_id=None,
            request_message=None,
            symbol=normalized_symbol,
            asset_type=payload.asset_type,
            risk_profile=payload.risk_profile,
            answer_text=None,
            workflow_steps=["api:recommendations"],
            recommendation=result,
            analysis=result.get("technical_snapshot", {}),
            market_context=None,
        )
        return RecommendationResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/news/{symbol}", response_model=NewsResponse)
def symbol_news(symbol: str, asset_type: str = "stock") -> NewsResponse:
    normalized_symbol = market_data_service.normalize_symbol(symbol=symbol, asset_type=asset_type)
    headlines = news_service.fetch_news(symbol=normalized_symbol, asset_type=asset_type)
    sentiment = news_service.sentiment_summary(headlines)
    return NewsResponse(
        symbol=normalized_symbol,
        asset_type=asset_type,
        headlines=[NewsItem(**item) for item in headlines],
        sentiment=NewsSentiment.model_validate(sentiment),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = chat_service.respond(
            message=payload.message,
            symbol=payload.symbol,
            asset_type=payload.asset_type,
            risk_profile=payload.risk_profile,
            session_id=payload.session_id,
            include_news=payload.include_news,
            include_alpha_context=payload.include_alpha_context,
            include_merged_news_sentiment=payload.include_merged_news_sentiment,
        )
        return ChatResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan/the-market", response_model=ScanTheMarketResponse)
def scan_the_market(payload: ScanTheMarketRequest) -> ScanTheMarketResponse:
    result = scan_the_market_service.scan(
        low_cap_max_usd=payload.low_cap_max_usd,
        stock_limit=payload.stock_limit,
        crypto_limit=payload.crypto_limit,
        include_ipo=payload.include_ipo,
        include_ico=payload.include_ico,
        include_news=payload.include_news,
        exchanges=payload.exchanges,
    )
    activity_log_service.log_market_scan(trigger_source="scan_api", payload=result)
    return ScanTheMarketResponse.model_validate(result)


@router.get("/market/alphavantage/context/{symbol}", response_model=AlphaVantageContextResponse)
def alphavantage_context(symbol: str, asset_type: str = "stock") -> AlphaVantageContextResponse:
    normalized_symbol = market_data_service.normalize_symbol(symbol=symbol, asset_type=asset_type)
    result = alphavantage_service.get_market_context(normalized_symbol)
    candles = result.get("candles", [])
    if not candles:
        frame = read_prices(normalized_symbol, limit=settings.alphavantage_daily_points)
        if not frame.empty:
            fallback_candles: list[dict[str, Any]] = []
            for row in frame.itertuples(index=False):
                timestamp = row.timestamp
                timestamp_str = (
                    timestamp.date().isoformat()
                    if hasattr(timestamp, "date")
                    else str(timestamp).split(" ")[0]
                )
                fallback_candles.append(
                    {
                        "date": timestamp_str,
                        "open": _to_float(row.open),
                        "high": _to_float(row.high),
                        "low": _to_float(row.low),
                        "close": _to_float(row.close),
                        "volume": _to_float(row.volume),
                    }
                )

            if fallback_candles:
                result["candles"] = fallback_candles
                if not result.get("trend"):
                    result["trend"] = alphavantage_service._build_trend(fallback_candles)
                result["source"] = "alphavantage-mcp+duckdb-fallback"
                warnings = result.get("warnings", [])
                warnings.append("AlphaVantage candles unavailable; using local DuckDB candles.")
                result["warnings"] = warnings
    return AlphaVantageContextResponse.model_validate(result)


@router.get("/integrations/status", response_model=IntegrationsStatusResponse)
def integrations_status() -> IntegrationsStatusResponse:
    runtime_controls_service.apply_runtime_overrides()
    usage = runtime_controls_service.chart_img_usage_stats()
    integrations: list[IntegrationStatusItem] = []

    timeseries_exists = Path(settings.timeseries_db_path).exists()
    integrations.append(
        IntegrationStatusItem(
            key="timeseries_db",
            label="Timeseries DB",
            state="up" if timeseries_exists else "warn",
            detail=(
                settings.timeseries_db_path
                if timeseries_exists
                else "DuckDB file not created yet."
            ),
        )
    )

    admin_exists = Path(settings.admin_db_path).exists()
    integrations.append(
        IntegrationStatusItem(
            key="admin_db",
            label="Admin DB",
            state="up" if admin_exists else "warn",
            detail=(
                settings.admin_db_path
                if admin_exists
                else "SQLite admin DB file not created yet."
            ),
        )
    )

    integrations.append(
        IntegrationStatusItem(
            key="serpapi",
            label="SerpAPI",
            state="up" if bool(settings.serpapi_api_key) else "warn",
            detail="Configured" if settings.serpapi_api_key else "Missing `SERPAPI_API_KEY`.",
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="alphavantage_mcp",
            label="AlphaVantage MCP",
            state=(
                "up"
                if bool(settings.alphavantage_api_key and settings.alphavantage_mcp_url)
                else "warn"
            ),
            detail=(
                settings.alphavantage_mcp_url
                if settings.alphavantage_api_key and settings.alphavantage_mcp_url
                else "Missing AlphaVantage MCP URL or API key."
            ),
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="alphavantage_rest",
            label="AlphaVantage REST",
            state=(
                "up"
                if bool(settings.alphavantage_api_key and settings.alphavantage_rest_url)
                else "warn"
            ),
            detail=(
                settings.alphavantage_rest_url
                if settings.alphavantage_api_key and settings.alphavantage_rest_url
                else "Missing AlphaVantage REST URL or API key."
            ),
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="chart_img",
            label="Chart-IMG",
            state="up" if bool(settings.chart_img_api_key) else "warn",
            detail=(
                (
                    f"{settings.chart_img_base_url} | version={settings.chart_img_api_version} | "
                    f"limit={settings.chart_img_daily_limit}/day | "
                    f"remaining={usage.get('remaining_today', 0)} | "
                    f"rate={settings.chart_img_rate_limit_per_sec}/sec | "
                    f"studies={settings.chart_img_max_studies} | "
                    f"max={settings.chart_img_max_width}x{settings.chart_img_max_height} | "
                    f"tests={'enabled' if settings.chart_img_tests_enabled else 'disabled'}"
                )
                if settings.chart_img_api_key
                else "Missing `CHART_IMG_API_KEY`."
            ),
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="coinmarketcap",
            label="CoinMarketCap",
            state="up" if bool(settings.coinmarketcap_api_key) else "warn",
            detail=(
                settings.coinmarketcap_base_url
                if settings.coinmarketcap_api_key
                else "Missing `COINMARKETCAP_API_KEY`."
            ),
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="openai",
            label="OpenAI",
            state="up" if bool(settings.openai_api_key) else "warn",
            detail=(
                f"Model {settings.openai_model}"
                if settings.openai_api_key
                else "Missing `OPENAI_API_KEY`."
            ),
        )
    )
    daemon_status = alert_daemon_service.get_status()
    daemon_state: Literal["up", "warn", "down"] = "warn"
    daemon_detail = "Alert daemon disabled."
    if bool(daemon_status.get("is_enabled", False)):
        last_heartbeat = daemon_status.get("last_heartbeat_at")
        running = bool(daemon_status.get("is_running", False))
        if running and last_heartbeat:
            parsed_heartbeat: datetime | None = None
            if isinstance(last_heartbeat, datetime):
                parsed_heartbeat = last_heartbeat
            elif isinstance(last_heartbeat, str):
                try:
                    parsed_heartbeat = datetime.fromisoformat(last_heartbeat)
                except ValueError:
                    parsed_heartbeat = None
            grace = max(
                int(settings.alert_daemon_heartbeat_grace_seconds),
                int(
                    daemon_status.get(
                        "frequency_seconds",
                        settings.alert_daemon_frequency_seconds,
                    )
                ),
            )
            if parsed_heartbeat is not None:
                heartbeat_dt = parsed_heartbeat
                if heartbeat_dt.tzinfo is None:
                    heartbeat_dt = heartbeat_dt.replace(tzinfo=UTC)
                else:
                    heartbeat_dt = heartbeat_dt.astimezone(UTC)
                heartbeat_age = (datetime.now(UTC) - heartbeat_dt).total_seconds()
                daemon_state = "up" if heartbeat_age <= (grace * 2) else "down"
            else:
                daemon_state = "warn"
        elif running:
            daemon_state = "warn"
        else:
            daemon_state = "warn"
        daemon_detail = (
            f"freq={daemon_status.get('frequency_seconds')}s | "
            f"cron={daemon_status.get('cron_hint')} | "
            f"status={daemon_status.get('last_cycle_status')} | "
            f"next={daemon_status.get('next_run_at')}"
        )
    integrations.append(
        IntegrationStatusItem(
            key="alert_daemon",
            label="Alert Daemon",
            state=daemon_state,
            detail=daemon_detail,
        )
    )
    integrations.append(
        IntegrationStatusItem(
            key="mcp_config",
            label="MCP Config",
            state="up" if Path("config/mcp.stocks.json").exists() else "warn",
            detail=(
                "config/mcp.stocks.json found."
                if Path("config/mcp.stocks.json").exists()
                else "config/mcp.stocks.json missing."
            ),
        )
    )

    overall = _overall_state([item.state for item in integrations])
    return IntegrationsStatusResponse(
        overall=overall,
        checked_at=datetime.now(UTC),
        integrations=integrations,
    )


@router.get("/admin/runtime/config", response_model=RuntimeConfigResponse)
def admin_runtime_config(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> RuntimeConfigResponse:
    payload = runtime_controls_service.get_runtime_config()
    return RuntimeConfigResponse.model_validate(payload)


@router.post("/admin/runtime/config", response_model=RuntimeConfigResponse)
def admin_update_runtime_config(
    payload: RuntimeConfigUpdateRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> RuntimeConfigResponse:
    updates = payload.model_dump(exclude_none=True)
    updated = runtime_controls_service.update_runtime_config(updates=updates)
    return RuntimeConfigResponse.model_validate(updated)


@router.get("/admin/openai/models", response_model=OpenAIModelCatalogResponse)
def admin_openai_models(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> OpenAIModelCatalogResponse:
    payload = runtime_controls_service.list_openai_models()
    return OpenAIModelCatalogResponse.model_validate(payload)


@router.post("/admin/openai/probe", response_model=RuntimeProbeResponse)
def admin_openai_probe(
    payload: RuntimeProbeRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> RuntimeProbeResponse:
    if not payload.model:
        raise HTTPException(status_code=400, detail="Model is required for OpenAI probe.")
    result = runtime_controls_service.probe_openai_model(model=payload.model)
    return RuntimeProbeResponse.model_validate(result)


@router.post("/admin/chart-img/probe", response_model=RuntimeProbeResponse)
def admin_chart_img_probe(
    payload: RuntimeProbeRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> RuntimeProbeResponse:
    if not settings.chart_img_tests_enabled:
        return RuntimeProbeResponse(
            success=False,
            target="chart_img",
            model="",
            latency_ms=0.0,
            detail="Chart-IMG probe is disabled by CHART_IMG_TESTS_ENABLED=false.",
        )
    result = runtime_controls_service.probe_chart_img(
        symbol=payload.symbol,
        asset_type=payload.asset_type,
        interval=payload.interval,
    )
    return RuntimeProbeResponse.model_validate(result)


@router.post("/admin/auth/login", response_model=AdminLoginResponse)
def admin_login(
    payload: AdminLoginRequest,
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminLoginResponse:
    auth = admin_auth_service.login(
        session=db,
        username=payload.username,
        password=payload.password,
    )
    if auth is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    user, token, expires_at = auth
    return AdminLoginResponse(
        token=token,
        username=user.username,
        email=user.email,
        role="admin" if user.role == "admin" else "user",
        subscription_ends_at=user.subscription_ends_at,
        subscription_active=_subscription_is_active(user),
        alerts_enabled=bool(user.alerts_enabled),
        mobile_phone=user.mobile_phone,
        expires_at=expires_at,
    )


@router.post("/admin/auth/logout", response_model=AdminLogoutResponse)
def admin_logout(
    authorization: str | None = Header(default=None),  # noqa: B008
    user: AdminUser = Depends(require_authenticated_user),  # noqa: ARG001, B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminLogoutResponse:
    token = _extract_bearer_token(authorization)
    if token:
        admin_auth_service.logout(session=db, token=token)
    return AdminLogoutResponse(status="ok")


@router.get("/admin/users", response_model=list[AdminUserRead])
def admin_list_users(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> list[AdminUserRead]:
    repo = AdminAuthRepository(db)
    return [_admin_user_to_schema(item) for item in repo.list_users()]


@router.post("/admin/users", response_model=AdminUserRead)
def admin_create_user(
    payload: AdminUserCreateRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminUserRead:
    repo = AdminAuthRepository(db)
    existing = repo.get_user_by_username(payload.username.strip())
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already exists.")
    if payload.email:
        existing_email = repo.get_user_by_email(payload.email.strip().lower())
        if existing_email is not None:
            raise HTTPException(status_code=400, detail="Email already exists.")
    created = admin_auth_service.create_user(
        session=db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        subscription_ends_at=payload.subscription_ends_at,
        alerts_enabled=payload.alerts_enabled,
        mobile_phone=payload.mobile_phone,
        is_active=payload.is_active,
    )
    return _admin_user_to_schema(created)


@router.patch("/admin/users/{user_id}", response_model=AdminUserRead)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminUserRead:
    repo = AdminAuthRepository(db)
    target = repo.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Admin user not found.")
    fields_set = payload.model_fields_set
    next_email = target.email
    next_mobile_phone = target.mobile_phone
    if "email" in fields_set:
        next_email = payload.email.strip().lower() if payload.email else None
    if "mobile_phone" in fields_set:
        next_mobile_phone = payload.mobile_phone.strip() if payload.mobile_phone else None
    if next_email:
        existing_email = repo.get_user_by_email(next_email)
        if existing_email is not None and existing_email.id != target.id:
            raise HTTPException(status_code=400, detail="Email already exists.")

    new_role = payload.role or target.role
    if new_role == "admin" and payload.is_active is False and repo.count_active_users() <= 1:
        raise HTTPException(status_code=400, detail="Cannot deactivate the last active admin user.")

    if (
        payload.is_active is False
        and target.role == "admin"
        and target.is_active
        and repo.count_active_users() <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot deactivate the last active admin user.")
    updated = admin_auth_service.update_user(
        session=db,
        user=target,
        email=next_email,
        password=payload.password,
        role=payload.role,
        subscription_ends_at=(
            payload.subscription_ends_at
            if "subscription_ends_at" in fields_set
            else target.subscription_ends_at
        ),
        alerts_enabled=(
            payload.alerts_enabled if "alerts_enabled" in fields_set else target.alerts_enabled
        ),
        mobile_phone=next_mobile_phone,
        is_active=payload.is_active,
    )
    return _admin_user_to_schema(updated)


@router.delete("/admin/users/{user_id}", response_model=AdminLogoutResponse)
def admin_delete_user(
    user_id: int,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminLogoutResponse:
    repo = AdminAuthRepository(db)
    target = repo.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Admin user not found.")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your current admin user.")
    if target.role == "admin" and target.is_active and repo.count_active_users() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last active admin user.")
    repo.delete_user(target)
    return AdminLogoutResponse(status="ok")


@router.get("/admin/db/tables", response_model=list[str])
def admin_db_tables(
    target_db: Literal["admin", "timeseries"] = "timeseries",
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> list[str]:
    summary = admin_tools_service.db_summary()
    if target_db == "admin":
        tables = summary.get("admin_tables", [])
        if isinstance(tables, list):
            return [str(item.get("table", "")) for item in tables if isinstance(item, dict)]
        return []

    import duckdb

    db_path = settings.timeseries_db_path
    rows: list[str] = []
    conn = duckdb.connect(db_path)
    try:
        result = conn.execute("SHOW TABLES").fetchall()
        for item in result:
            if item and item[0]:
                rows.append(str(item[0]))
    finally:
        conn.close()
    return rows


@router.get("/admin/db/summary", response_model=AdminDbSummaryResponse)
def admin_db_summary(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AdminDbSummaryResponse:
    return AdminDbSummaryResponse.model_validate(admin_tools_service.db_summary())


@router.post("/admin/tests/run", response_model=AdminTestRunResponse)
def admin_run_tests(
    payload: AdminTestRunRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AdminTestRunResponse:
    result = admin_tools_service.run_test_suite(suite=payload.suite)
    return AdminTestRunResponse.model_validate(result)


@router.post("/admin/db/query", response_model=AdminDbQueryResponse)
def admin_db_query(
    payload: AdminDbQueryRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AdminDbQueryResponse:
    try:
        result = admin_tools_service.run_db_query(
            target_db=payload.target_db,
            sql=payload.sql,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminDbQueryResponse.model_validate(result)


@router.get("/admin/logs", response_model=AdminLogsResponse)
def admin_logs(
    level: Literal["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "ALL",
    limit: int = 250,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AdminLogsResponse:
    result = admin_tools_service.read_logs(level=level, limit=limit)
    return AdminLogsResponse.model_validate(result)


@router.get("/admin/alerts/subscriptions", response_model=list[AlertSubscriptionRead])
def admin_list_alert_subscriptions(
    mine_only: bool = True,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> list[AlertSubscriptionRead]:
    repo = AdminOpsRepository(db)
    user_id = user.id if (mine_only or user.role != "admin") else None
    rows = repo.list_alert_subscriptions(user_id=user_id)
    return [_alert_to_schema(subscription=row[0], username=row[1]) for row in rows]


@router.post("/admin/alerts/subscriptions", response_model=AlertSubscriptionRead)
def admin_create_alert_subscription(
    payload: AlertSubscriptionCreateRequest,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AlertSubscriptionRead:
    repo = AdminOpsRepository(db)
    created = repo.create_alert_subscription(
        user_id=user.id,
        symbol=payload.symbol.strip().upper(),
        asset_type=payload.asset_type,
        alert_scope=payload.alert_scope,
        rule_key=payload.rule_key.strip().lower() if payload.rule_key else None,
        metric=payload.metric.strip().lower(),
        operator=payload.operator,
        threshold=payload.threshold,
        frequency_seconds=payload.frequency_seconds,
        timeframe=payload.timeframe,
        lookback_period=payload.lookback_period.strip().lower(),
        cooldown_minutes=payload.cooldown_minutes,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    return _alert_to_schema(subscription=created, username=user.username)


@router.patch("/admin/alerts/subscriptions/{subscription_id}", response_model=AlertSubscriptionRead)
def admin_update_alert_subscription(
    subscription_id: int,
    payload: AlertSubscriptionUpdateRequest,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AlertSubscriptionRead:
    repo = AdminOpsRepository(db)
    target = repo.get_alert_subscription(subscription_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Alert subscription not found.")
    if user.role != "admin" and target.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this subscription.")
    fields_set = payload.model_fields_set

    updated = repo.update_alert_subscription(
        subscription=target,
        asset_type=payload.asset_type if "asset_type" in fields_set else target.asset_type,
        alert_scope=payload.alert_scope if "alert_scope" in fields_set else target.alert_scope,
        rule_key=(
            payload.rule_key.strip().lower()
            if ("rule_key" in fields_set and payload.rule_key)
            else (None if "rule_key" in fields_set else target.rule_key)
        ),
        metric=payload.metric if "metric" in fields_set else target.metric,
        operator=payload.operator if "operator" in fields_set else target.operator,
        threshold=payload.threshold if "threshold" in fields_set else target.threshold,
        frequency_seconds=(
            payload.frequency_seconds
            if "frequency_seconds" in fields_set
            else target.frequency_seconds
        ),
        timeframe=payload.timeframe if "timeframe" in fields_set else target.timeframe,
        lookback_period=(
            payload.lookback_period.strip().lower()
            if ("lookback_period" in fields_set and payload.lookback_period)
            else target.lookback_period
        ),
        cooldown_minutes=(
            payload.cooldown_minutes
            if "cooldown_minutes" in fields_set
            else target.cooldown_minutes
        ),
        notes=payload.notes if "notes" in fields_set else target.notes,
        is_active=payload.is_active if "is_active" in fields_set else target.is_active,
    )
    username = user.username
    if user.role == "admin" and target.user_id != user.id:
        owner = AdminAuthRepository(db).get_user_by_id(target.user_id)
        if owner is not None:
            username = owner.username
    return _alert_to_schema(subscription=updated, username=username)


@router.delete("/admin/alerts/subscriptions/{subscription_id}", response_model=AdminLogoutResponse)
def admin_delete_alert_subscription(
    subscription_id: int,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> AdminLogoutResponse:
    repo = AdminOpsRepository(db)
    target = repo.get_alert_subscription(subscription_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Alert subscription not found.")
    if user.role != "admin" and target.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this subscription.")
    repo.delete_alert_subscription(target)
    return AdminLogoutResponse(status="ok")


@router.get("/admin/alerts/daemon/status", response_model=AlertDaemonStatusResponse)
def admin_alert_daemon_status(
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> AlertDaemonStatusResponse:
    return AlertDaemonStatusResponse.model_validate(alert_daemon_service.get_status())


@router.post("/admin/alerts/daemon/run", response_model=AlertDaemonRunResponse)
def admin_alert_daemon_run(
    payload: AlertDaemonRunRequest,
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AlertDaemonRunResponse:
    result = alert_daemon_service.run_cycle(trigger_source=payload.trigger_source)
    return AlertDaemonRunResponse.model_validate(result)


@router.post("/admin/alerts/daemon/start", response_model=AlertDaemonStatusResponse)
def admin_alert_daemon_start(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AlertDaemonStatusResponse:
    return AlertDaemonStatusResponse.model_validate(alert_daemon_service.start_background_loop())


@router.post("/admin/alerts/daemon/stop", response_model=AlertDaemonStatusResponse)
def admin_alert_daemon_stop(
    user: AdminUser = Depends(require_admin_user),  # noqa: ARG001, B008
) -> AlertDaemonStatusResponse:
    return AlertDaemonStatusResponse.model_validate(alert_daemon_service.stop_background_loop())


@router.get("/admin/alerts/daemon/rules", response_model=list[AlertRuleRead])
def admin_alert_daemon_rules(
    include_inactive: bool = False,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> list[AlertRuleRead]:
    rows = alert_daemon_service.list_rules(include_inactive=include_inactive)
    return [
        AlertRuleRead(
            id=item.id,
            rule_key=item.rule_key,
            name=item.name,
            description=item.description,
            category=item.category,
            asset_type=item.asset_type,
            timeframe=item.timeframe,
            horizon=item.horizon,
            action=item.action,
            severity=item.severity,
            priority=item.priority,
            expression_json=item.expression_json,
            data_requirements=item.data_requirements,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]


@router.get("/admin/alerts/daemon/cycles", response_model=list[AlertDaemonCycleRead])
def admin_alert_daemon_cycles(
    limit: int = 50,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> list[AlertDaemonCycleRead]:
    rows = alert_daemon_service.list_cycles(limit=limit)
    return [AlertDaemonCycleRead.model_validate(item) for item in rows]


@router.get("/admin/alerts/daemon/triggers", response_model=list[AlertTriggerLogRead])
def admin_alert_daemon_triggers(
    cycle_id: str | None = None,
    symbol: str | None = None,
    user_id: int | None = None,
    limit: int = 200,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> list[AlertTriggerLogRead]:
    effective_user_id = user_id
    if user.role != "admin":
        effective_user_id = user.id
    rows = alert_daemon_service.list_triggers(
        cycle_id=cycle_id,
        symbol=symbol,
        user_id=effective_user_id,
        limit=limit,
    )
    return [AlertTriggerLogRead.model_validate(item) for item in rows]


@router.get("/admin/alerts/daemon/snapshots", response_model=list[AlertAnalysisSnapshotRead])
def admin_alert_daemon_snapshots(
    cycle_id: str | None = None,
    symbol: str | None = None,
    limit: int = 200,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> list[AlertAnalysisSnapshotRead]:
    rows = alert_daemon_service.list_analysis_snapshots(
        cycle_id=cycle_id,
        symbol=symbol,
        limit=limit,
    )
    return [AlertAnalysisSnapshotRead.model_validate(item) for item in rows]


@router.get("/admin/alerts/daemon/agent-feed", response_model=AlertAgentFeedResponse)
def admin_alert_daemon_agent_feed(
    after_id: int = 0,
    limit: int = 25,
    user: AdminUser = Depends(require_admin_or_subscribed_user),  # noqa: ARG001, B008
) -> AlertAgentFeedResponse:
    rows = alert_daemon_service.list_agent_events(after_id=after_id, limit=limit)
    next_after_id = max([after_id] + [int(item.get("id", 0)) for item in rows])
    return AlertAgentFeedResponse(
        items=[AlertAgentEventRead.model_validate(item) for item in rows],
        next_after_id=next_after_id,
    )


@router.get("/alerts/agent-feed", response_model=AlertAgentFeedResponse)
def alert_agent_feed(after_id: int = 0, limit: int = 25) -> AlertAgentFeedResponse:
    rows = alert_daemon_service.list_agent_events(after_id=after_id, limit=limit)
    next_after_id = max([after_id] + [int(item.get("id", 0)) for item in rows])
    return AlertAgentFeedResponse(
        items=[AlertAgentEventRead.model_validate(item) for item in rows],
        next_after_id=next_after_id,
    )


@router.post("/portfolio/positions", response_model=PositionRead)
def create_position(
    payload: PositionCreate,
    db: Session = Depends(get_db_session),  # noqa: B008
) -> PositionRead:
    repo = PortfolioRepository(db)
    saved = repo.create_position(payload)
    return PositionRead(
        id=saved.id,
        user_id=saved.user_id,
        symbol=saved.symbol,
        asset_type=saved.asset_type,
        quantity=saved.quantity,
        avg_price=saved.avg_price,
    )


@router.get("/portfolio/{user_id}/positions", response_model=list[PositionRead])
def list_positions(
    user_id: int,
    db: Session = Depends(get_db_session),  # noqa: B008
) -> list[PositionRead]:
    repo = PortfolioRepository(db)
    rows = repo.list_positions(user_id)
    return [
        PositionRead(
            id=r.id,
            user_id=r.user_id,
            symbol=r.symbol,
            asset_type=r.asset_type,
            quantity=r.quantity,
            avg_price=r.avg_price,
        )
        for r in rows
    ]

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/v1")
PROMPT_CONFIG_PATH = os.getenv("PROMPT_CONFIG_PATH", "config/prompt_shortcuts.json")
CHART_IMG_TESTS_ENABLED = _env_bool("CHART_IMG_TESTS_ENABLED", False)
THEME_MODES = ["light", "dark"]
DEFAULT_UI_THEME = os.getenv("UI_THEME_MODE", "light").strip().lower()
if DEFAULT_UI_THEME not in THEME_MODES:
    DEFAULT_UI_THEME = "light"

ASSET_TYPES = ["stock", "crypto", "etf"]
SECTIONS = ["Chat", "Admin", "Alerts"]
RISK_PROFILES = ["conservative", "balanced", "aggressive"]
SNAPSHOT_PERIODS = ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
SNAPSHOT_INTERVALS = ["5m", "15m", "30m", "60m", "1d", "1wk"]
ALERT_TIMEFRAMES = ["15m", "1h", "4h", "1d", "1wk"]
CHART_IMG_VERSIONS = ["v2"]
DIVERGENCE_MODES = ["conservative", "balanced", "aggressive"]
SNAPSHOT_METRICS = [
    "latest_close",
    "latest_open",
    "latest_high",
    "latest_low",
    "market_cap",
    "sma_15",
    "sma_20",
    "sma_30",
    "sma_50",
    "sma_100",
    "sma_200",
    "ema_15",
    "ema_30",
    "ema_50",
    "ema_100",
    "ema_200",
    "rsi_14",
    "rsi_30",
    "macd",
    "macd_signal",
    "volume",
    "momentum_10",
    "momentum_30",
    "volatility_20",
    "atr_14",
    "vwma_20",
    "bb_upper_20",
    "bb_lower_20",
    "bb_percent_b_20",
    "adx_14",
    "obv",
    "mfi_14",
    "stoch_k_14",
    "stoch_d_14",
    "cci_20",
    "williams_r_14",
    "roc_10",
]
DEFAULT_SNAPSHOT_METRICS = [
    "latest_close",
    "market_cap",
    "sma_20",
    "ema_50",
    "rsi_14",
    "macd",
    "volume",
]
DEFAULT_QUICK_PROMPTS = [
    "Should I buy AAPL for the next 2 weeks?",
    "Long-term outlook for NVDA for 12 months.",
    "Compare BTC and ETH for a balanced portfolio.",
    "Where are the key support and resistance levels for SPY?",
    "What are the major risk factors for TSLA right now?",
    "Show me a candle image for NVDA with SMA, EMA, RSI and MACD.",
    "ScanTheMarket: scan stocks and crypto with CoinMarketCap + IPO/ICO + news signals.",
]
INITIAL_ASSISTANT_MESSAGE = (
    "Ask short or long-term opportunities for any ticker. "
    "Example: 'Should I buy NVDA for the next 2 weeks?'"
)
try:
    CONVERSATION_BOX_HEIGHT = max(420, int(os.getenv("CHAT_CONVERSATION_HEIGHT", "620")))
except ValueError:
    CONVERSATION_BOX_HEIGHT = 620


def load_prompt_shortcuts() -> list[str]:
    path = Path(PROMPT_CONFIG_PATH)
    if not path.exists():
        return list(DEFAULT_QUICK_PROMPTS)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(DEFAULT_QUICK_PROMPTS)

    rows: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            text = str(item).strip()
            if text:
                rows.append(text)
    elif isinstance(payload, dict):
        prompts = payload.get("prompts", [])
        if isinstance(prompts, list):
            for item in prompts:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                else:
                    text = str(item).strip()
                if text:
                    rows.append(text)

    if rows:
        return rows
    return list(DEFAULT_QUICK_PROMPTS)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _symbol_option_label(item: dict[str, Any]) -> str:
    symbol = str(item.get("symbol", "")).upper()
    name = str(item.get("name", ""))
    asset_type = str(item.get("asset_type", "")).lower()
    return f"{symbol} | {name} [{asset_type}]"


def _extract_symbol_from_label(label: str) -> str:
    return label.split("|", 1)[0].strip().upper()


def _extract_asset_type_from_label(label: str) -> str | None:
    if "[" not in label or "]" not in label:
        return None
    chunk = label.rsplit("[", 1)[-1].split("]", 1)[0].strip().lower()
    if chunk in ASSET_TYPES:
        return chunk
    return None


def _is_chart_request(message: str) -> bool:
    lowered = message.lower()
    tokens = [
        "candle",
        "candlestick",
        "tradingview",
        "diagram",
        "chart image",
        "chart-img",
        "chart img",
        "price chart",
        "show chart",
        "show me a chart",
    ]
    return any(token in lowered for token in tokens)


def _api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[Any | None, str | None, int | None]:
    url = f"{API_BASE}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        return None, f"Connection error: {exc}", None

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.is_success:
        if payload is not None:
            return payload, None, response.status_code
        return response.text, None, response.status_code

    detail = response.text
    if isinstance(payload, dict) and "detail" in payload:
        detail = str(payload["detail"])
    return None, detail, response.status_code


@st.cache_data(ttl=60)
def fetch_system_info() -> dict[str, Any] | None:
    payload, error, _ = _api_request("GET", "/system/info")
    if error or not isinstance(payload, dict):
        return None
    return payload


@st.cache_data(ttl=120)
def fetch_symbol_suggestions(query: str, limit: int = 250) -> list[dict[str, Any]]:
    payload, error, _ = _api_request(
        "GET",
        "/market/symbol-search",
        params={"q": query, "limit": limit},
    )
    if error or not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


@st.cache_data(ttl=120)
def fetch_market_snapshot(
    symbol: str,
    asset_type: str,
    period: str,
    interval: str,
    metrics_csv: str,
) -> dict[str, Any] | None:
    payload, error, _ = _api_request(
        "GET",
        f"/market/snapshot/{symbol}",
        params={
            "asset_type": asset_type,
            "period": period,
            "interval": interval,
            "metrics": metrics_csv,
        },
        timeout=45.0,
    )
    if error or not isinstance(payload, dict):
        return None
    return payload


@st.cache_data(ttl=120)
def fetch_alphavantage_context(symbol: str, asset_type: str) -> dict[str, Any] | None:
    payload, error, _ = _api_request(
        "GET",
        f"/market/alphavantage/context/{symbol}",
        params={"asset_type": asset_type},
        timeout=45.0,
    )
    if error or not isinstance(payload, dict):
        return None
    return payload


@st.cache_data(ttl=120)
def fetch_candle_image(
    symbol: str,
    asset_type: str,
    interval: str,
    metrics_csv: str,
    theme: str,
) -> dict[str, Any] | None:
    payload, error, _ = _api_request(
        "GET",
        f"/market/candle-image/{symbol}",
        params={
            "asset_type": asset_type,
            "interval": interval,
            "theme": theme,
            "studies": metrics_csv,
            "width": 800,
            "height": 600,
        },
        timeout=60.0,
    )
    if error or not isinstance(payload, dict):
        return None
    return payload


@st.cache_data(ttl=120)
def fetch_serp_news(symbol: str, asset_type: str) -> dict[str, Any] | None:
    payload, error, _ = _api_request(
        "GET",
        f"/news/{symbol}",
        params={"asset_type": asset_type},
        timeout=30.0,
    )
    if error or not isinstance(payload, dict):
        return None
    return payload


@st.cache_data(ttl=90)
def fetch_integrations_status() -> dict[str, Any] | None:
    payload, error, _ = _api_request("GET", "/integrations/status")
    if error or not isinstance(payload, dict):
        return None
    return payload


def fetch_alert_agent_feed(after_id: int = 0, limit: int = 20) -> dict[str, Any] | None:
    payload, error, _ = _api_request(
        "GET",
        "/alerts/agent-feed",
        params={"after_id": after_id, "limit": limit},
        timeout=20.0,
    )
    if error or not isinstance(payload, dict):
        return None
    return payload


def _admin_headers() -> dict[str, str] | None:
    token = str(st.session_state.get("admin_token", "")).strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def admin_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> tuple[Any | None, str | None, int | None]:
    headers = _admin_headers()
    if headers is None:
        return None, "Admin login is required.", None

    payload, error, status = _api_request(
        method,
        path,
        params=params,
        json_data=json_data,
        headers=headers,
        timeout=timeout,
    )
    if status == 401:
        st.session_state.admin_token = ""
        st.session_state.admin_username = ""
        st.session_state.admin_role = ""
        st.session_state.admin_email = ""
        st.session_state.admin_subscription_ends_at = ""
        st.session_state.admin_subscription_active = False
        st.session_state.admin_alerts_enabled = False
        st.session_state.admin_mobile_phone = ""
        st.session_state.admin_runtime_config = None
        st.session_state.admin_model_catalog = None
        st.session_state.admin_probe_result = None
        st.session_state.admin_selected_divergence_mode = "aggressive"
        st.session_state.daemon_status_payload = None
        st.session_state.daemon_cycles_payload = None
        st.session_state.daemon_triggers_payload = None
        st.session_state.daemon_rules_payload = None
        st.session_state.daemon_snapshots_payload = None
        st.session_state.daemon_run_result = None
        st.session_state.admin_trigger_symbol_filter = ""
        st.session_state.admin_trigger_user_filter = ""
        return None, "Admin session expired. Please login again.", status
    return payload, error, status


def render_state_dot(state: str) -> str:
    colors = {"up": "#16a34a", "warn": "#f59e0b", "down": "#dc2626"}
    color = colors.get(state, "#6b7280")
    return (
        f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
        f"background:{color};margin-right:8px;vertical-align:middle;'></span>"
    )


def render_base_css(theme_mode: str) -> None:
    is_dark = theme_mode == "dark"
    app_bg = "#030712" if is_dark else "#f3f4f6"
    sidebar_bg = "#111827" if is_dark else "#e5e7eb"
    text_primary = "#f9fafb" if is_dark else "#111827"
    text_secondary = "#cbd5e1" if is_dark else "#4b5563"
    border_color = "#334155" if is_dark else "#d9e2f2"
    banner_bg = (
        "linear-gradient(90deg, #111827 0%, #1f2937 100%)"
        if is_dark
        else "linear-gradient(90deg, #f8fafc 0%, #eef2ff 100%)"
    )
    card_bg = "#0f172a" if is_dark else "#f8fafc"
    footer_bg = (
        "linear-gradient(180deg, rgba(3, 7, 18, 0.0) 0%, rgba(3, 7, 18, 0.96) 18%)"
        if is_dark
        else "linear-gradient(180deg, rgba(243, 244, 246, 0.0) 0%, rgba(243, 244, 246, 0.98) 18%)"
    )
    footer_text = "#f9fafb" if is_dark else "#111827"
    footer_button_bg = "#0f172a" if is_dark else "#ffffff"
    footer_button_text = "#f9fafb" if is_dark else "#111827"
    footer_input_bg = "#111827" if is_dark else "#ffffff"
    footer_input_text = "#f9fafb" if is_dark else "#111827"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {app_bg};
            color: {text_primary};
        }}
        section[data-testid="stSidebar"] {{
            background: {sidebar_bg};
        }}
        .fr-banner {{
            position: sticky;
            top: 0;
            z-index: 1000;
            background: {banner_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 14px;
        }}
        .fr-banner h2 {{
            margin: 0;
            font-size: 1.4rem;
            color: {text_primary};
        }}
        .fr-banner p {{
            margin: 2px 0 0 0;
            font-size: 0.85rem;
            color: {text_secondary};
        }}
        .fr-author a {{
            color: {"#93c5fd" if is_dark else "#1d4ed8"};
            text-decoration: none;
            font-weight: 600;
        }}
        .fr-author a:hover {{
            text-decoration: underline;
        }}
        .fr-card {{
            border: 1px solid {border_color};
            border-radius: 10px;
            background: {card_bg};
            padding: 10px;
            margin-bottom: 8px;
        }}
        .fr-card-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: {text_primary};
            margin-bottom: 2px;
        }}
        .fr-card-sub {{
            font-size: 0.8rem;
            color: {text_secondary};
        }}
        .st-key-chat_footer {{
            position: sticky;
            bottom: 0;
            z-index: 1002;
            padding-top: 10px;
            background: {footer_bg};
        }}
        .st-key-chat_footer h3,
        .st-key-chat_footer p,
        .st-key-chat_footer label,
        .st-key-chat_footer span {{
            color: {footer_text} !important;
        }}
        .st-key-chat_footer div[data-testid="stButton"] > button {{
            background: {footer_button_bg};
            color: {footer_button_text};
            border: 1px solid {border_color};
        }}
        .st-key-chat_footer div[data-testid="stButton"] > button[kind="primary"] {{
            background: #ef4444;
            color: #ffffff;
            border: 1px solid #ef4444;
        }}
        .st-key-chat_footer div[data-testid="stTextInputRootElement"] input {{
            background: {footer_input_bg} !important;
            color: {footer_input_text} !important;
            border: 1px solid {border_color};
        }}
        .st-key-chat_footer div[data-testid="stTextInputRootElement"] input::placeholder {{
            color: {text_secondary} !important;
        }}
        .main .block-container {{
            padding-bottom: 220px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_banner(system_info: dict[str, Any] | None) -> None:
    app_name = "Financial Recommender"
    app_version = "0.2"
    env = "dev"
    author_name = "Luis Medinelli"
    author_url = "https://medinelli.ai"
    if system_info:
        app_name = str(system_info.get("app", app_name))
        app_version = str(system_info.get("version", app_version))
        env = str(system_info.get("env", env))
        author_name = str(system_info.get("author_name", author_name))
        author_url = str(system_info.get("author_url", author_url))
    st.markdown(
        (
            "<div class='fr-banner'>"
            f"<h2>{app_name} v{app_version}</h2>"
            "<p class='fr-author'>"
            f"Author: <a href='{author_url}' target='_blank'>{author_name}</a>"
            "</p>"
            f"<p>Environment: {env} | Decision support only, not financial advice.</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults: dict[str, Any] = {
        "ui_theme_mode": DEFAULT_UI_THEME,
        "active_section": "Chat",
        "symbol": "AAPL",
        "asset_type": "stock",
        "symbol_combo": "AAPL",
        "risk_profile": "balanced",
        "include_news": True,
        "include_alpha_context": True,
        "include_merged_news_sentiment": True,
        "snapshot_period": "6mo",
        "snapshot_interval": "1d",
        "snapshot_metrics": list(DEFAULT_SNAPSHOT_METRICS),
        "chat_session_id": "",
        "messages": [
            {
                "role": "assistant",
                "content": INITIAL_ASSISTANT_MESSAGE,
            }
        ],
        "draft_message": "",
        "queued_prompt": "",
        "clear_draft_after_send": False,
        "latest_chat_payload": None,
        "admin_token": "",
        "admin_username": "",
        "admin_email": "",
        "admin_role": "",
        "admin_subscription_ends_at": "",
        "admin_subscription_active": False,
        "admin_alerts_enabled": False,
        "admin_mobile_phone": "",
        "admin_query_result": None,
        "admin_test_result": None,
        "admin_logs_payload": None,
        "admin_logs_signature": "",
        "admin_runtime_config": None,
        "admin_model_catalog": None,
        "admin_probe_result": None,
        "admin_selected_openai_model": "",
        "admin_selected_divergence_mode": "aggressive",
        "admin_selected_chart_version": "v2",
        "admin_chart_max_width": 800,
        "admin_chart_max_height": 600,
        "admin_chart_max_studies": 3,
        "admin_chart_rate_limit_per_sec": 1.0,
        "admin_chart_daily_limit": 50,
        "admin_chart_enforce_limits": True,
        "show_candle_image": False,
        "latest_candle_image_payload": None,
        "latest_candle_image_error": "",
        "latest_candle_image_symbol": "",
        "latest_candle_image_asset_type": "stock",
        "latest_candle_image_interval": "1D",
        "admin_query_table": "",
        "alert_feed_after_id": 0,
        "alert_feed_events": [],
        "daemon_status_payload": None,
        "daemon_cycles_payload": None,
        "daemon_triggers_payload": None,
        "daemon_rules_payload": None,
        "daemon_snapshots_payload": None,
        "daemon_run_result": None,
        "admin_trigger_symbol_filter": "",
        "admin_trigger_user_filter": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar() -> dict[str, Any]:
    with st.sidebar:
        section = st.segmented_control(
            "Workspace",
            options=SECTIONS,
            default=st.session_state.active_section,
            width="stretch",
        )
        if isinstance(section, str) and section in SECTIONS:
            st.session_state.active_section = section

        theme_mode = st.segmented_control(
            "Theme",
            options=THEME_MODES,
            default=str(st.session_state.ui_theme_mode),
            format_func=lambda value: str(value).title(),
            width="stretch",
        )
        if isinstance(theme_mode, str) and theme_mode in THEME_MODES:
            st.session_state.ui_theme_mode = theme_mode

        st.markdown("### Symbol Selector")
        suggestions = fetch_symbol_suggestions(query="", limit=250)
        option_labels: list[str] = []
        option_map: dict[str, dict[str, Any]] = {}
        for item in suggestions:
            label = _symbol_option_label(item)
            option_labels.append(label)
            option_map[label] = item

        if not option_labels:
            option_labels = [st.session_state.symbol]

        symbol_combo = st.selectbox(
            "Search Symbol or Name",
            options=option_labels,
            key="symbol_combo",
            accept_new_options=True,
            width="stretch",
        )

        selected_label = str(symbol_combo)
        selected_item = option_map.get(selected_label)
        if selected_item:
            st.session_state.symbol = str(selected_item.get("symbol", "AAPL")).upper()
            selected_asset = str(selected_item.get("asset_type", "stock")).lower()
            if selected_asset in ASSET_TYPES:
                st.session_state.asset_type = selected_asset
        else:
            symbol_raw = _extract_symbol_from_label(selected_label)
            st.session_state.symbol = symbol_raw or "AAPL"
            inferred_asset = _extract_asset_type_from_label(selected_label)
            if inferred_asset in ASSET_TYPES:
                st.session_state.asset_type = inferred_asset

        st.caption(f"Selected symbol: {st.session_state.symbol}")

        st.session_state.asset_type = st.selectbox(
            "Asset Type",
            ASSET_TYPES,
            index=ASSET_TYPES.index(st.session_state.asset_type),
            width="stretch",
        )

        if st.session_state.active_section == "Chat":
            st.markdown("### Active Strategy")
            st.markdown(
                (
                    "<div class='fr-card'>"
                    f"<div class='fr-card-title'>Risk: {st.session_state.risk_profile}</div>"
                    f"<div class='fr-card-sub'>News={st.session_state.include_news} | "
                    f"MCP={st.session_state.include_alpha_context} | "
                    f"Merged Sentiment={st.session_state.include_merged_news_sentiment}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            st.info("Advanced settings moved to Admin section.")

    return {
        "section": st.session_state.active_section,
        "symbol": st.session_state.symbol,
        "asset_type": st.session_state.asset_type,
    }


def render_market_snapshot(symbol: str, asset_type: str) -> None:
    st.markdown("### Market Snapshot")
    metrics = st.session_state.snapshot_metrics or list(DEFAULT_SNAPSHOT_METRICS)
    metrics_csv = ",".join(metrics)
    snapshot = fetch_market_snapshot(
        symbol=symbol,
        asset_type=asset_type,
        period=st.session_state.snapshot_period,
        interval=st.session_state.snapshot_interval,
        metrics_csv=metrics_csv,
    )
    if snapshot is None:
        st.warning("Could not load yFinance market snapshot for this symbol/period/interval.")
        return

    selected_metrics = snapshot.get("selected_metrics", [])
    if not isinstance(selected_metrics, list) or not selected_metrics:
        st.info("No snapshot metrics returned.")
        return

    history_points = int(snapshot.get("history_points", 5))
    history_points = max(2, min(history_points, 8))
    history_labels = snapshot.get("history_labels", [])
    if not isinstance(history_labels, list):
        history_labels = []

    rows: list[dict[str, Any]] = []
    chart_rows: list[dict[str, Any]] = []
    trend_colors = {
        "improving": "#16a34a",
        "worsening": "#dc2626",
        "equal": "#eab308",
    }
    period_opacity = [0.35, 0.5, 0.65, 0.82, 1.0]
    while len(period_opacity) < history_points:
        period_opacity.append(1.0)
    fallback_labels = [f"T-{history_points - idx - 1}" for idx in range(history_points)]

    for item in selected_metrics:
        if not isinstance(item, dict):
            continue
        metric_name = str(item.get("metric", "")).strip()
        if not metric_name:
            continue
        trend_status = str(item.get("trend_status", "equal")).lower()
        if trend_status not in trend_colors:
            trend_status = "equal"
        trend_delta = _safe_float(item.get("trend_delta", 0.0))
        trend_color = trend_colors[trend_status]
        history = item.get("history", [])
        points: list[dict[str, Any]] = []
        if isinstance(history, list):
            for point in history:
                if isinstance(point, dict):
                    points.append(point)

        labels = history_labels[:]
        if len(labels) != history_points:
            labels = [str(p.get("label", "")) for p in points if isinstance(p, dict)]
        if len(labels) != history_points:
            labels = fallback_labels

        values = [_safe_float(point.get("value", 0.0)) for point in points[:history_points]]
        while len(values) < history_points:
            values.insert(0, 0.0)

        max_abs = max(1.0, max(abs(value) for value in values))
        normalized_values = [(value / max_abs) * 100.0 for value in values]

        table_row: dict[str, Any] = {
            "metric": metric_name,
            "trend_status": trend_status,
            "trend_delta": round(trend_delta, 6),
        }
        for idx in range(history_points):
            label = labels[idx] if idx < len(labels) else fallback_labels[idx]
            value = values[idx]
            normalized = normalized_values[idx]
            table_row[label] = value
            chart_rows.append(
                {
                    "metric": metric_name,
                    "period_label": label,
                    "period_index": idx,
                    "raw_value": value,
                    "normalized_value": normalized,
                    "trend_color": trend_color,
                    "trend_status": trend_status,
                }
            )

        table_row["current_value"] = values[-1]
        table_row["delta_vs_previous"] = values[-1] - values[-2]
        rows.append(table_row)

    if not rows or not chart_rows:
        st.info("Snapshot metric list is empty.")
        return

    frame = pd.DataFrame(chart_rows)
    fig = go.Figure()
    for idx in range(history_points):
        period_frame = frame[frame["period_index"] == idx]
        if period_frame.empty:
            continue
        legend_label = str(period_frame["period_label"].iloc[0])
        fig.add_trace(
            go.Bar(
                x=period_frame["metric"],
                y=period_frame["normalized_value"],
                name=legend_label,
                marker_color=list(period_frame["trend_color"]),
                opacity=period_opacity[idx],
                customdata=period_frame["raw_value"],
                hovertemplate=(
                    "Metric=%{x}<br>"
                    "Period=%{fullData.name}<br>"
                    "Raw=%{customdata}<br>"
                    "Normalized=%{y:.2f}%<extra></extra>"
                ),
            )
        )
    for label, color in [
        ("Improving metric trend", trend_colors["improving"]),
        ("Worsening metric trend", trend_colors["worsening"]),
        ("Stable metric trend", trend_colors["equal"]),
    ]:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"size": 10, "color": color},
                name=label,
            )
        )
    fig.update_layout(
        barmode="group",
        height=360,
        margin={"l": 8, "r": 8, "t": 20, "b": 8},
        yaxis_title="Relative scale per metric (%)",
        legend_title="5-period view",
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Each metric shows 5 consecutive periods. "
        "Color indicates trend status (green=improving, red=worsening, yellow=stable). "
        "Opacity increases from oldest to newest period."
    )

    table = pd.DataFrame(rows)
    table["period"] = str(snapshot.get("period", st.session_state.snapshot_period))
    table["interval"] = str(snapshot.get("interval", st.session_state.snapshot_interval))
    table["sample_size"] = int(snapshot.get("sample_size", 0))
    table["last_timestamp"] = str(snapshot.get("last_timestamp", ""))
    st.dataframe(table, width="stretch")
    st.caption(
        "On-demand Chart-IMG calls are disabled in snapshot refresh. "
        "Ask for a candle/tradingview chart in chat to trigger one request."
    )


def _to_chart_img_interval(interval: str) -> str:
    key = interval.strip().lower()
    mapping = {
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "1h",
        "1d": "1D",
        "1wk": "1W",
    }
    return mapping.get(key, "1D")


def render_context_news(symbol: str, asset_type: str) -> None:
    if st.session_state.include_news:
        st.markdown("### SerpAPI News")
        news_data = fetch_serp_news(symbol=symbol, asset_type=asset_type)
        if news_data and isinstance(news_data.get("headlines"), list):
            headlines = news_data.get("headlines", [])
            if headlines:
                for item in headlines[:6]:
                    title = str(item.get("title", ""))
                    source = str(item.get("source", "Unknown"))
                    url = str(item.get("url", ""))
                    st.markdown(f"- [{title}]({url}) ({source})")
            else:
                st.info("SerpAPI returned no headlines.")
        else:
            st.info("SerpAPI context unavailable.")

    if st.session_state.include_alpha_context:
        st.markdown("### AlphaVantage MCP Context")
        context = fetch_alphavantage_context(symbol=symbol, asset_type=asset_type)
        if context is None:
            st.info("AlphaVantage context unavailable.")
            return

        trend = context.get("trend") or {}
        quote = context.get("quote") or {}
        c1, c2 = st.columns(2)
        c1.metric(
            "Live Price",
            f"{_safe_float(quote.get('price', 0.0)):.2f}",
            f"{_safe_float(quote.get('change_percent', 0.0)):+.2f}%",
        )
        c2.metric(
            "Trend",
            str(trend.get("direction", "unknown")).upper(),
            f"30d={_safe_float(trend.get('change_pct_30d', 0.0)):+.2f}%",
        )

        alpha_news = context.get("news", [])
        if isinstance(alpha_news, list) and alpha_news:
            for item in alpha_news[:6]:
                title = str(item.get("title", ""))
                url = str(item.get("url", ""))
                source = str(item.get("source", ""))
                st.markdown(f"- [{title}]({url}) ({source})")

        warnings = context.get("warnings", [])
        if isinstance(warnings, list) and warnings:
            st.warning(
                "AlphaVantage warnings:\n- "
                + "\n- ".join([str(item) for item in warnings[:3]])
            )


def render_prompt_shortcuts() -> None:
    prompts = load_prompt_shortcuts()
    if not prompts:
        st.info("No prompt shortcuts configured.")
        return
    cols = st.columns(2)
    for idx, prompt in enumerate(prompts):
        with cols[idx % 2]:
            if st.button(prompt, key=f"quick_prompt_{idx}", width="stretch"):
                st.session_state.queued_prompt = prompt
                st.rerun()


def ingest_proactive_alert_events() -> None:
    after_id = int(st.session_state.get("alert_feed_after_id", 0))
    payload = fetch_alert_agent_feed(after_id=after_id, limit=12)
    if not isinstance(payload, dict):
        return
    rows = payload.get("items", [])
    if not isinstance(rows, list):
        return
    posted = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message", "")).strip()
        if not message:
            continue
        event_type = str(item.get("event_type", "")).strip().lower()
        prefix = "[Daemon]"
        if event_type == "trigger":
            prefix = "[Alert Trigger]"
        elif event_type == "cycle_summary":
            prefix = "[Daemon Cycle]"
        st.session_state.messages.append({"role": "assistant", "content": f"{prefix} {message}"})
        posted += 1

    if posted > 0:
        st.session_state.alert_feed_events = rows
    next_after = int(payload.get("next_after_id", after_id))
    st.session_state.alert_feed_after_id = max(after_id, next_after)


def render_chat_history() -> None:
    st.markdown("### Conversation")
    history_box = st.container(height=CONVERSATION_BOX_HEIGHT, border=True)
    with history_box:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        latest = st.session_state.latest_chat_payload
        if isinstance(latest, dict):
            workflow_steps = latest.get("workflow_steps", [])
            if isinstance(workflow_steps, list) and workflow_steps:
                with st.expander("Workflow Trace", expanded=False):
                    st.code("\n".join([str(item) for item in workflow_steps]), language="text")

            recommendation = latest.get("recommendation", {})
            if isinstance(recommendation, dict):
                short = recommendation.get("short_term", {})
                long = recommendation.get("long_term", {})
                sentiment = recommendation.get("news_sentiment", {})
                cols = st.columns(3)
                cols[0].metric(
                    "Short-Term",
                    str((short or {}).get("action", "n/a")).upper(),
                    f"{_safe_float((short or {}).get('confidence', 0.0)):.0%}",
                )
                cols[1].metric(
                    "Long-Term",
                    str((long or {}).get("action", "n/a")).upper(),
                    f"{_safe_float((long or {}).get('confidence', 0.0)):.0%}",
                )
                cols[2].metric(
                    "Merged News Sentiment",
                    str((sentiment or {}).get("label", "neutral")).upper(),
                    f"{_safe_float((sentiment or {}).get('score', 0.0)):+.2f}",
                )

            market_scan = latest.get("market_scan", {})
            if isinstance(market_scan, dict) and market_scan:
                st.markdown("### ScanTheMarket Results")
                top_stocks = market_scan.get("stock_opportunities", [])
                if isinstance(top_stocks, list) and top_stocks:
                    st.markdown("Top Stock Opportunities")
                    st.dataframe(pd.DataFrame(top_stocks), width="stretch")

                top_crypto = market_scan.get("crypto_opportunities", [])
                if isinstance(top_crypto, list) and top_crypto:
                    st.markdown("Top Crypto Opportunities")
                    st.dataframe(pd.DataFrame(top_crypto), width="stretch")

            if bool(st.session_state.get("show_candle_image", False)):
                st.markdown("### Candle Chart (On-demand)")
                payload = st.session_state.get("latest_candle_image_payload")
                if isinstance(payload, dict):
                    encoded = str(payload.get("image_base64", ""))
                    symbol_caption = str(
                        payload.get(
                            "tradingview_symbol",
                            st.session_state.get("latest_candle_image_symbol", ""),
                        )
                    )
                    if encoded:
                        try:
                            st.image(
                                base64.b64decode(encoded),
                                caption=f"Chart-IMG {symbol_caption}",
                                width="stretch",
                            )
                        except Exception:
                            st.info("Candle image payload could not be decoded.")
                    else:
                        st.info("Candle image response did not include image data.")
                else:
                    error_text = str(st.session_state.get("latest_candle_image_error", "")).strip()
                    if error_text:
                        st.info(error_text)


def _update_on_demand_candle_image(
    *,
    chart_requested: bool,
    response: dict[str, Any],
    fallback_symbol: str,
    fallback_asset_type: str,
) -> None:
    if not chart_requested:
        st.session_state.show_candle_image = False
        st.session_state.latest_candle_image_payload = None
        st.session_state.latest_candle_image_error = ""
        st.session_state.latest_candle_image_symbol = ""
        st.session_state.latest_candle_image_asset_type = "stock"
        st.session_state.latest_candle_image_interval = "1D"
        return

    resolved_symbol_raw = str(response.get("symbol", fallback_symbol)).strip().upper()
    resolved_symbol = resolved_symbol_raw or fallback_symbol
    resolved_asset_type = str(response.get("asset_type", fallback_asset_type)).strip().lower()
    if resolved_asset_type not in ASSET_TYPES:
        resolved_asset_type = fallback_asset_type
    chart_interval = _to_chart_img_interval(st.session_state.snapshot_interval)
    metrics_csv = ",".join(st.session_state.snapshot_metrics or list(DEFAULT_SNAPSHOT_METRICS))
    chart_theme = "dark" if st.session_state.ui_theme_mode == "dark" else "light"
    image_payload = fetch_candle_image(
        symbol=resolved_symbol,
        asset_type=resolved_asset_type,
        interval=chart_interval,
        metrics_csv=metrics_csv,
        theme=chart_theme,
    )

    st.session_state.show_candle_image = True
    st.session_state.latest_candle_image_symbol = resolved_symbol
    st.session_state.latest_candle_image_asset_type = resolved_asset_type
    st.session_state.latest_candle_image_interval = chart_interval
    if image_payload:
        st.session_state.latest_candle_image_payload = image_payload
        st.session_state.latest_candle_image_error = ""
    else:
        st.session_state.latest_candle_image_payload = None
        st.session_state.latest_candle_image_error = (
            "Candle image unavailable. Check Chart-IMG limits/quota and API credentials."
        )


def send_current_message(symbol: str, asset_type: str) -> None:
    message = str(st.session_state.draft_message).strip()
    if len(message) < 3:
        st.warning("Message should have at least 3 characters.")
        return
    chart_requested = _is_chart_request(message)

    st.session_state.messages.append({"role": "user", "content": message})
    payload = {
        "message": message,
        "session_id": st.session_state.chat_session_id or None,
        "symbol": symbol,
        "asset_type": asset_type,
        "risk_profile": st.session_state.risk_profile,
        "include_news": bool(st.session_state.include_news),
        "include_alpha_context": bool(st.session_state.include_alpha_context),
        "include_merged_news_sentiment": bool(st.session_state.include_merged_news_sentiment),
    }
    response, error, _ = _api_request("POST", "/chat", json_data=payload, timeout=90.0)
    if error:
        st.session_state.messages.append({"role": "assistant", "content": error})
        _update_on_demand_candle_image(
            chart_requested=False,
            response={},
            fallback_symbol=symbol,
            fallback_asset_type=asset_type,
        )
        return
    if not isinstance(response, dict):
        st.session_state.messages.append(
            {"role": "assistant", "content": "Unexpected chat response payload."}
        )
        _update_on_demand_candle_image(
            chart_requested=False,
            response={},
            fallback_symbol=symbol,
            fallback_asset_type=asset_type,
        )
        return

    st.session_state.chat_session_id = str(
        response.get("session_id", st.session_state.chat_session_id)
    )
    st.session_state.messages.append(
        {"role": "assistant", "content": str(response.get("answer", ""))}
    )
    st.session_state.latest_chat_payload = response
    _update_on_demand_candle_image(
        chart_requested=chart_requested,
        response=response,
        fallback_symbol=symbol,
        fallback_asset_type=asset_type,
    )
    st.session_state.clear_draft_after_send = True


def clear_chat_conversation() -> None:
    st.session_state.messages = [{"role": "assistant", "content": INITIAL_ASSISTANT_MESSAGE}]
    st.session_state.latest_chat_payload = None
    st.session_state.chat_session_id = ""
    st.session_state.queued_prompt = ""
    st.session_state.show_candle_image = False
    st.session_state.latest_candle_image_payload = None
    st.session_state.latest_candle_image_error = ""
    st.session_state.latest_candle_image_symbol = ""
    st.session_state.latest_candle_image_asset_type = "stock"
    st.session_state.latest_candle_image_interval = "1D"
    st.session_state.clear_draft_after_send = True


def render_chat_input(symbol: str, asset_type: str) -> None:
    footer = st.container(key="chat_footer")
    with footer:
        st.markdown("### Prompt Shortcuts")
        render_prompt_shortcuts()
        st.markdown("### Ask the Assistant")
        if st.session_state.clear_draft_after_send:
            st.session_state.draft_message = ""
            st.session_state.clear_draft_after_send = False
        queued = str(st.session_state.get("queued_prompt", "")).strip()
        if queued:
            st.session_state.draft_message = queued
            st.session_state.queued_prompt = ""

        st.text_input(
            "Ask about any stock or crypto opportunity",
            key="draft_message",
            placeholder="Type your question or click a prompt shortcut...",
            label_visibility="collapsed",
        )
        send_col, clear_col = st.columns([4, 1])
        with send_col:
            if st.button("Send", type="primary", width="stretch"):
                send_current_message(symbol=symbol, asset_type=asset_type)
                st.rerun()
        with clear_col:
            if st.button("Clear Chat", width="stretch"):
                clear_chat_conversation()
                st.rerun()


def render_chat_page(symbol: str, asset_type: str) -> None:
    ingest_proactive_alert_events()
    render_market_snapshot(symbol=symbol, asset_type=asset_type)
    render_context_news(symbol=symbol, asset_type=asset_type)
    render_chat_history()
    render_chat_input(symbol=symbol, asset_type=asset_type)


def render_integration_cards(status_payload: dict[str, Any] | None) -> None:
    if not status_payload:
        st.warning("Integration status unavailable.")
        return

    overall = str(status_payload.get("overall", "warn")).upper()
    st.caption(f"Integration Semaphore overall={overall}")

    items = status_payload.get("integrations", [])
    if not isinstance(items, list):
        st.info("No integration data returned.")
        return

    cols = st.columns(min(4, max(1, len(items))))
    for idx, item in enumerate(items):
        col = cols[idx % len(cols)]
        with col:
            state = str(item.get("state", "warn"))
            label = str(item.get("label", item.get("key", "integration")))
            detail = str(item.get("detail", ""))
            st.markdown(
                (
                    "<div class='fr-card'>"
                    f"<div class='fr-card-title'>{render_state_dot(state)}{label}</div>"
                    f"<div class='fr-card-sub'>{detail}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def render_admin_login() -> None:
    st.markdown("### Control Access Login")
    with st.form("admin_login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", value="", type="password")
        submit = st.form_submit_button("Login", width="stretch")

    if submit:
        payload, error, _ = _api_request(
            "POST",
            "/admin/auth/login",
            json_data={"username": username, "password": password},
            timeout=30.0,
        )
        if error or not isinstance(payload, dict):
            st.error(error or "Login failed.")
            return
        st.session_state.admin_token = str(payload.get("token", ""))
        st.session_state.admin_username = str(payload.get("username", username))
        st.session_state.admin_email = str(payload.get("email", ""))
        st.session_state.admin_role = str(payload.get("role", "user"))
        st.session_state.admin_subscription_ends_at = str(payload.get("subscription_ends_at", ""))
        st.session_state.admin_subscription_active = bool(payload.get("subscription_active", False))
        st.session_state.admin_alerts_enabled = bool(payload.get("alerts_enabled", False))
        st.session_state.admin_mobile_phone = str(payload.get("mobile_phone", ""))
        st.success("Login successful.")
        st.rerun()


def render_admin_settings(symbol: str, asset_type: str) -> None:
    st.markdown("#### Strategy & Snapshot Settings")
    st.session_state.risk_profile = st.selectbox(
        "Risk Profile",
        RISK_PROFILES,
        index=RISK_PROFILES.index(st.session_state.risk_profile),
        width="stretch",
    )
    st.session_state.include_news = st.checkbox(
        "Use News Context (SerpAPI)",
        value=bool(st.session_state.include_news),
    )
    st.session_state.include_alpha_context = st.checkbox(
        "Use AlphaVantage MCP Context",
        value=bool(st.session_state.include_alpha_context),
    )
    st.session_state.include_merged_news_sentiment = st.checkbox(
        "Merge NEWS_SENTIMENT (SerpAPI + AlphaVantage)",
        value=bool(st.session_state.include_merged_news_sentiment),
    )

    st.session_state.snapshot_period = st.selectbox(
        "Snapshot Period",
        SNAPSHOT_PERIODS,
        index=SNAPSHOT_PERIODS.index(st.session_state.snapshot_period),
        width="stretch",
    )
    st.session_state.snapshot_interval = st.selectbox(
        "Snapshot Interval",
        SNAPSHOT_INTERVALS,
        index=SNAPSHOT_INTERVALS.index(st.session_state.snapshot_interval),
        width="stretch",
    )
    selected_metrics = st.multiselect(
        "Snapshot Metrics",
        SNAPSHOT_METRICS,
        default=st.session_state.snapshot_metrics,
    )
    st.session_state.snapshot_metrics = selected_metrics or list(DEFAULT_SNAPSHOT_METRICS)

    if st.button("Ingest / Refresh Market Data", width="stretch"):
        payload, error, _ = _api_request(
            "POST",
            f"/market/ingest/{symbol}",
            params={"asset_type": asset_type},
            timeout=60.0,
        )
        if error:
            st.error(error)
        else:
            st.success(payload)
            fetch_market_snapshot.clear()
            fetch_alphavantage_context.clear()
            fetch_serp_news.clear()


def render_admin_data_query() -> None:
    st.markdown("#### Direct Database Query")
    target = st.selectbox("Target DB", ["timeseries", "admin"], width="stretch")
    tables_payload, tables_error, _ = admin_request(
        "GET",
        "/admin/db/tables",
        params={"target_db": target},
        timeout=30.0,
    )
    table_options: list[str] = []
    if isinstance(tables_payload, list):
        table_options = [str(item) for item in tables_payload if str(item).strip()]
    if not table_options:
        table_options = ["prices" if target == "timeseries" else "admin_users"]

    default_table = st.session_state.get("admin_query_table", table_options[0])
    if default_table not in table_options:
        default_table = table_options[0]
    selected_table = st.selectbox(
        "Table",
        options=table_options,
        index=table_options.index(default_table),
        width="stretch",
    )
    st.session_state.admin_query_table = selected_table

    default_sql = f"SELECT * FROM {selected_table} LIMIT 25"
    if tables_error:
        st.caption(f"Table list warning: {tables_error}")
    sql = st.text_area("Read-only SQL", value=default_sql, height=120)
    limit = st.number_input("Row Limit", min_value=1, max_value=2000, value=200, step=10)

    if st.button("Run Query", type="primary", width="stretch"):
        payload, error, _ = admin_request(
            "POST",
            "/admin/db/query",
            json_data={"target_db": target, "sql": sql, "limit": int(limit)},
            timeout=60.0,
        )
        if error:
            st.error(error)
            st.session_state.admin_query_result = None
        else:
            st.session_state.admin_query_result = payload

    result = st.session_state.get("admin_query_result")
    if isinstance(result, dict):
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        if isinstance(columns, list) and isinstance(rows, list):
            frame = pd.DataFrame(rows, columns=columns)
            st.dataframe(frame, width="stretch")
            st.caption(
                f"Rows={result.get('row_count', 0)} | Truncated={result.get('truncated', False)}"
            )


def render_admin_users() -> None:
    st.markdown("#### Admin Users")
    users_payload, error, _ = admin_request("GET", "/admin/users", timeout=30.0)
    if error:
        st.error(error)
        return

    users: list[dict[str, Any]] = []
    if isinstance(users_payload, list):
        users = [item for item in users_payload if isinstance(item, dict)]

    if users:
        users_frame = pd.DataFrame(users)
        st.dataframe(users_frame, width="stretch")

    with st.form("create_admin_user_form"):
        st.markdown("Create User")
        username = st.text_input("New Username")
        email = st.text_input("Email (optional)")
        mobile_phone = st.text_input("Mobile Phone (optional)")
        password = st.text_input("New Password", type="password")
        role = st.selectbox("Role", ["user", "admin"], width="stretch")
        subscription_ends_at = st.text_input(
            "Subscription Ends At (optional, ISO datetime)",
            placeholder="2026-12-31T23:59:59",
        )
        alerts_enabled = st.checkbox("Alerts Enabled", value=False)
        is_active = st.checkbox("Active", value=True)
        create_submit = st.form_submit_button("Create User", width="stretch")
    if create_submit:
        payload: dict[str, Any] = {
            "username": username,
            "email": email or None,
            "mobile_phone": mobile_phone.strip() or None,
            "password": password,
            "role": role,
            "alerts_enabled": alerts_enabled,
            "is_active": is_active,
        }
        if subscription_ends_at.strip():
            payload["subscription_ends_at"] = subscription_ends_at.strip()
        payload, create_error, _ = admin_request(
            "POST",
            "/admin/users",
            json_data=payload,
        )
        if create_error:
            st.error(create_error)
        else:
            st.success(f"User created: {payload.get('username', '')}")
            st.rerun()

    if not users:
        return

    st.markdown("Update / Delete User")
    user_options = {f"{item['id']} | {item['username']}": item for item in users}
    selected_label = st.selectbox("Select User", list(user_options.keys()), width="stretch")
    selected_user = user_options[selected_label]

    with st.form("update_admin_user_form"):
        email_value = str(selected_user.get("email", "") or "")
        new_email = st.text_input("Email", value=email_value)
        mobile_value = str(selected_user.get("mobile_phone", "") or "")
        new_mobile_phone = st.text_input("Mobile Phone", value=mobile_value)
        role_value = str(selected_user.get("role", "user"))
        selected_role = st.selectbox(
            "Role",
            ["user", "admin"],
            index=0 if role_value != "admin" else 1,
            width="stretch",
        )
        subscription_value = str(selected_user.get("subscription_ends_at", "") or "")
        new_subscription = st.text_input(
            "Subscription Ends At (ISO datetime)",
            value=subscription_value,
            placeholder="2026-12-31T23:59:59",
        )
        current_alerts_enabled = bool(selected_user.get("alerts_enabled", False))
        new_alerts_enabled = st.checkbox("Alerts Enabled", value=current_alerts_enabled)
        new_password = st.text_input("New Password (optional)", type="password")
        updated_active = st.checkbox("Active", value=bool(selected_user.get("is_active", True)))
        update_submit = st.form_submit_button("Update User", width="stretch")
    if update_submit:
        payload = {
            "email": new_email.strip() or None,
            "mobile_phone": new_mobile_phone.strip() or None,
            "role": selected_role,
            "is_active": updated_active,
            "subscription_ends_at": new_subscription.strip() or None,
            "alerts_enabled": new_alerts_enabled,
        }
        if new_password.strip():
            payload["password"] = new_password.strip()
        _, update_error, _ = admin_request(
            "PATCH",
            f"/admin/users/{selected_user['id']}",
            json_data=payload,
        )
        if update_error:
            st.error(update_error)
        else:
            st.success("User updated.")
            st.rerun()

    if st.button("Delete Selected User", width="stretch"):
        _, delete_error, _ = admin_request(
            "DELETE",
            f"/admin/users/{selected_user['id']}",
        )
        if delete_error:
            st.error(delete_error)
        else:
            st.success("User deleted.")
            st.rerun()


def _sync_runtime_state(config_payload: dict[str, Any]) -> None:
    st.session_state.admin_runtime_config = config_payload
    st.session_state.admin_selected_openai_model = str(
        config_payload.get("openai_model", st.session_state.admin_selected_openai_model)
    )
    mode_value = str(
        config_payload.get(
            "alert_divergence_15m_mode",
            st.session_state.admin_selected_divergence_mode,
        )
    ).strip().lower()
    if mode_value not in DIVERGENCE_MODES:
        mode_value = "balanced"
    st.session_state.admin_selected_divergence_mode = mode_value
    st.session_state.admin_selected_chart_version = str(
        config_payload.get("chart_img_api_version", st.session_state.admin_selected_chart_version)
    )
    st.session_state.admin_chart_max_width = int(
        config_payload.get("chart_img_max_width", st.session_state.admin_chart_max_width)
    )
    st.session_state.admin_chart_max_height = int(
        config_payload.get("chart_img_max_height", st.session_state.admin_chart_max_height)
    )
    st.session_state.admin_chart_max_studies = int(
        config_payload.get("chart_img_max_studies", st.session_state.admin_chart_max_studies)
    )
    st.session_state.admin_chart_rate_limit_per_sec = float(
        config_payload.get(
            "chart_img_rate_limit_per_sec",
            st.session_state.admin_chart_rate_limit_per_sec,
        )
    )
    st.session_state.admin_chart_daily_limit = int(
        config_payload.get("chart_img_daily_limit", st.session_state.admin_chart_daily_limit)
    )
    st.session_state.admin_chart_enforce_limits = bool(
        config_payload.get("chart_img_enforce_limits", st.session_state.admin_chart_enforce_limits)
    )


def render_admin_diagnostics(symbol: str, asset_type: str) -> None:
    st.markdown("#### Integrations & API Probe")
    integration_payload = fetch_integrations_status()
    render_integration_cards(integration_payload)

    st.markdown("#### Runtime Controls")
    runtime_payload, runtime_error, _ = admin_request(
        "GET",
        "/admin/runtime/config",
        timeout=30.0,
    )
    if runtime_error:
        st.error(runtime_error)
    elif isinstance(runtime_payload, dict):
        _sync_runtime_state(runtime_payload)

    model_catalog_payload, model_catalog_error, _ = admin_request(
        "GET",
        "/admin/openai/models",
        timeout=45.0,
    )
    if model_catalog_error:
        st.caption(f"OpenAI model catalog warning: {model_catalog_error}")
    elif isinstance(model_catalog_payload, dict):
        st.session_state.admin_model_catalog = model_catalog_payload

    model_options = list(
        dict.fromkeys(
            [
                str(item)
                for item in (
                    (st.session_state.admin_model_catalog or {}).get("models", [])
                    if isinstance(st.session_state.admin_model_catalog, dict)
                    else []
                )
                if str(item).strip()
            ]
            + [str(st.session_state.admin_selected_openai_model).strip()]
        )
    )
    if not model_options:
        model_options = [str(st.session_state.admin_selected_openai_model or "gpt-4.1")]
    selected_model = st.selectbox(
        "OpenAI Model",
        options=model_options,
        index=model_options.index(str(st.session_state.admin_selected_openai_model))
        if str(st.session_state.admin_selected_openai_model) in model_options
        else 0,
        width="stretch",
    )
    st.session_state.admin_selected_openai_model = selected_model

    selected_divergence_mode = st.selectbox(
        "15m Divergence Sensitivity",
        DIVERGENCE_MODES,
        index=DIVERGENCE_MODES.index(st.session_state.admin_selected_divergence_mode)
        if st.session_state.admin_selected_divergence_mode in DIVERGENCE_MODES
        else 2,
        width="stretch",
        format_func=lambda value: str(value).title(),
        help=(
            "Conservative = fewer signals, Aggressive = more signals. "
            "Used by 15m RSI/MACD divergence alert rules."
        ),
    )
    st.session_state.admin_selected_divergence_mode = selected_divergence_mode

    col_model_save, col_model_probe, col_mode_save = st.columns(3)
    with col_model_save:
        if st.button("Save OpenAI Model", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/runtime/config",
                json_data={"openai_model": st.session_state.admin_selected_openai_model},
                timeout=30.0,
            )
            if error:
                st.error(error)
            elif isinstance(payload, dict):
                _sync_runtime_state(payload)
                fetch_integrations_status.clear()
                st.success(f"OpenAI model set to {payload.get('openai_model', '')}.")
    with col_model_probe:
        if st.button("Probe OpenAI Model", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/openai/probe",
                json_data={"model": st.session_state.admin_selected_openai_model},
                timeout=60.0,
            )
            if error:
                st.error(error)
            else:
                st.session_state.admin_probe_result = payload
    with col_mode_save:
        if st.button("Save Divergence Mode", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/runtime/config",
                json_data={
                    "alert_divergence_15m_mode": st.session_state.admin_selected_divergence_mode
                },
                timeout=30.0,
            )
            if error:
                st.error(error)
            elif isinstance(payload, dict):
                _sync_runtime_state(payload)
                st.success(
                    "15m divergence mode set to "
                    f"{payload.get('alert_divergence_15m_mode', '')}."
                )

    chart_version = st.selectbox(
        "Chart-IMG API Version",
        CHART_IMG_VERSIONS,
        index=CHART_IMG_VERSIONS.index(st.session_state.admin_selected_chart_version)
        if st.session_state.admin_selected_chart_version in CHART_IMG_VERSIONS
        else 0,
        width="stretch",
    )
    st.session_state.admin_selected_chart_version = chart_version
    st.caption("Chart-IMG runtime is locked to v2 in this release.")

    col_w, col_h, col_s = st.columns(3)
    with col_w:
        st.session_state.admin_chart_max_width = int(
            st.number_input(
                "Chart max width",
                min_value=400,
                max_value=4096,
                value=int(st.session_state.admin_chart_max_width),
                step=50,
            )
        )
    with col_h:
        st.session_state.admin_chart_max_height = int(
            st.number_input(
                "Chart max height",
                min_value=300,
                max_value=2160,
                value=int(st.session_state.admin_chart_max_height),
                step=50,
            )
        )
    with col_s:
        st.session_state.admin_chart_max_studies = int(
            st.number_input(
                "Chart max studies",
                min_value=1,
                max_value=25,
                value=int(st.session_state.admin_chart_max_studies),
                step=1,
            )
        )

    col_rate, col_daily, col_enforce = st.columns(3)
    with col_rate:
        st.session_state.admin_chart_rate_limit_per_sec = float(
            st.number_input(
                "Chart rate limit / sec",
                min_value=0.1,
                max_value=100.0,
                value=float(st.session_state.admin_chart_rate_limit_per_sec),
                step=0.1,
                format="%.1f",
            )
        )
    with col_daily:
        st.session_state.admin_chart_daily_limit = int(
            st.number_input(
                "Chart daily limit",
                min_value=1,
                max_value=10000,
                value=int(st.session_state.admin_chart_daily_limit),
                step=1,
            )
        )
    with col_enforce:
        st.session_state.admin_chart_enforce_limits = st.checkbox(
            "Enforce chart limits",
            value=bool(st.session_state.admin_chart_enforce_limits),
        )

    col_chart_save, col_chart_probe = st.columns(2)
    with col_chart_save:
        if st.button("Save Chart-IMG Runtime", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/runtime/config",
                json_data={
                    "chart_img_api_version": st.session_state.admin_selected_chart_version,
                    "chart_img_max_width": st.session_state.admin_chart_max_width,
                    "chart_img_max_height": st.session_state.admin_chart_max_height,
                    "chart_img_max_studies": st.session_state.admin_chart_max_studies,
                    "chart_img_rate_limit_per_sec": st.session_state.admin_chart_rate_limit_per_sec,
                    "chart_img_daily_limit": st.session_state.admin_chart_daily_limit,
                    "chart_img_enforce_limits": st.session_state.admin_chart_enforce_limits,
                },
                timeout=30.0,
            )
            if error:
                st.error(error)
            elif isinstance(payload, dict):
                _sync_runtime_state(payload)
                fetch_integrations_status.clear()
                max_width = payload.get("chart_img_max_width")
                max_height = payload.get("chart_img_max_height")
                max_studies = payload.get("chart_img_max_studies")
                st.success(
                    "Chart-IMG runtime updated: "
                    f"version={payload.get('chart_img_api_version')} "
                    f"max={max_width}x{max_height} "
                    f"studies={max_studies}"
                )
    with col_chart_probe:
        if not CHART_IMG_TESTS_ENABLED:
            st.button("Probe Chart-IMG", width="stretch", disabled=True)
            st.caption("Chart-IMG probes are disabled by CHART_IMG_TESTS_ENABLED=false.")
        elif st.button("Probe Chart-IMG", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/chart-img/probe",
                json_data={
                    "symbol": symbol,
                    "asset_type": asset_type,
                    "interval": _to_chart_img_interval(st.session_state.snapshot_interval),
                },
                timeout=90.0,
            )
            if error:
                st.error(error)
            else:
                st.session_state.admin_probe_result = payload

    runtime_cfg = st.session_state.get("admin_runtime_config")
    if isinstance(runtime_cfg, dict):
        calls_today = runtime_cfg.get("chart_img_calls_today", 0)
        daily_limit = runtime_cfg.get("chart_img_daily_limit", 0)
        remaining_today = runtime_cfg.get("chart_img_remaining_today", 0)
        st.caption(
            "Chart-IMG usage today: "
            f"{calls_today} / {daily_limit} "
            f"(remaining {remaining_today})"
        )
        st.caption(
            f"OpenAI configured model: {runtime_cfg.get('openai_model', '')} | "
            f"15m divergence mode: {runtime_cfg.get('alert_divergence_15m_mode', '')} | "
            f"Last runtime update: {runtime_cfg.get('updated_at', 'n/a')}"
        )

    probe_result = st.session_state.get("admin_probe_result")
    if isinstance(probe_result, dict):
        detail = str(probe_result.get("detail", ""))
        target = str(probe_result.get("target", "probe"))
        latency_ms = _safe_float(probe_result.get("latency_ms", 0.0))
        if bool(probe_result.get("success", False)):
            st.success(f"{target} probe OK in {latency_ms:.1f}ms")
        else:
            st.error(f"{target} probe failed in {latency_ms:.1f}ms")
        st.caption(detail)

    if st.button("Run API Probe", width="stretch"):
        checks: list[tuple[str, bool, str]] = []
        endpoints_to_probe: list[tuple[str, dict[str, Any] | None]] = [
            ("/health", None),
            (
                f"/market/snapshot/{symbol}",
                {
                    "asset_type": asset_type,
                    "period": st.session_state.snapshot_period,
                    "interval": st.session_state.snapshot_interval,
                    "metrics": ",".join(st.session_state.snapshot_metrics),
                },
            ),
            (f"/news/{symbol}", {"asset_type": asset_type}),
            (f"/market/alphavantage/context/{symbol}", {"asset_type": asset_type}),
            (
                "/admin/openai/probe",
                {"model": st.session_state.admin_selected_openai_model},
            ),
        ]
        if CHART_IMG_TESTS_ENABLED:
            endpoints_to_probe.append(
                (
                    f"/market/candle-image/{symbol}",
                    {
                        "asset_type": asset_type,
                        "interval": _to_chart_img_interval(st.session_state.snapshot_interval),
                        "studies": ",".join(
                            st.session_state.snapshot_metrics[
                                : st.session_state.admin_chart_max_studies
                            ]
                        ),
                    },
                )
            )
        else:
            checks.append(
                (
                    "/market/candle-image/{symbol}",
                    True,
                    "Skipped by CHART_IMG_TESTS_ENABLED=false",
                )
            )

        for endpoint, params in endpoints_to_probe:
            method = "GET"
            payload: Any | None
            error: str | None
            if endpoint == "/admin/openai/probe":
                method = "POST"
                payload, error, _ = admin_request(
                    method,
                    endpoint,
                    json_data=params,
                    timeout=60.0,
                )
            else:
                payload, error, _ = _api_request(method, endpoint, params=params, timeout=45.0)
            checks.append((endpoint, error is None, str(payload if error is None else error)[:160]))

        for endpoint, ok, detail in checks:
            if ok:
                st.success(f"{endpoint} OK")
            else:
                st.error(f"{endpoint} FAILED")
            st.caption(detail)

    st.markdown("#### Test Runner")
    suite = st.selectbox("Suite", ["smoke", "unit", "integration", "all"], width="stretch")
    if st.button("Run Backend Tests", type="primary", width="stretch"):
        payload, error, _ = admin_request(
            "POST",
            "/admin/tests/run",
            json_data={"suite": suite},
            timeout=300.0,
        )
        if error:
            st.error(error)
            st.session_state.admin_test_result = None
        else:
            st.session_state.admin_test_result = payload

    result = st.session_state.get("admin_test_result")
    if isinstance(result, dict):
        status = str(result.get("status", "error"))
        duration = _safe_float(result.get("duration_seconds", 0.0))
        if status == "passed":
            st.success(f"Tests passed in {duration:.2f}s")
        elif status == "failed":
            st.error(f"Tests failed in {duration:.2f}s")
        elif status == "timeout":
            st.warning(f"Tests timed out after {duration:.2f}s")
        else:
            st.warning(f"Test status: {status}")
        st.caption(str(result.get("command", "")))
        st.code(str(result.get("output_tail", "")), language="text")


def render_admin_alert_daemon() -> None:
    st.markdown("#### Alert Daemon Monitor")
    status_payload, status_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/status",
        timeout=30.0,
    )
    if status_error:
        st.error(status_error)
        return
    if not isinstance(status_payload, dict):
        st.warning("Daemon status payload unavailable.")
        return

    st.session_state.daemon_status_payload = status_payload
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enabled", "YES" if bool(status_payload.get("is_enabled")) else "NO")
    c2.metric("Running", "UP" if bool(status_payload.get("is_running")) else "DOWN")
    c3.metric("Frequency (sec)", int(status_payload.get("frequency_seconds", 0)))
    c4.metric("Run Count", int(status_payload.get("run_count", 0)))
    st.caption(
        f"Cron hint: {status_payload.get('cron_hint', '')} | "
        f"Last cycle status: {status_payload.get('last_cycle_status', 'n/a')} | "
        f"Next run: {status_payload.get('next_run_at', 'n/a')}"
    )

    ctl1, ctl2, ctl3 = st.columns(3)
    with ctl1:
        if st.button("Run Cycle Now", type="primary", width="stretch"):
            payload, error, _ = admin_request(
                "POST",
                "/admin/alerts/daemon/run",
                json_data={"trigger_source": "manual"},
                timeout=120.0,
            )
            if error:
                st.error(error)
            else:
                st.session_state.daemon_run_result = payload
                fetch_integrations_status.clear()
                st.success("Manual cycle executed.")
                st.rerun()
    with ctl2:
        if st.button("Start Daemon", width="stretch"):
            _, error, _ = admin_request(
                "POST",
                "/admin/alerts/daemon/start",
                timeout=30.0,
            )
            if error:
                st.error(error)
            else:
                fetch_integrations_status.clear()
                st.success("Daemon started.")
                st.rerun()
    with ctl3:
        if st.button("Stop Daemon", width="stretch"):
            _, error, _ = admin_request(
                "POST",
                "/admin/alerts/daemon/stop",
                timeout=30.0,
            )
            if error:
                st.error(error)
            else:
                fetch_integrations_status.clear()
                st.success("Daemon stopped.")
                st.rerun()

    run_result = st.session_state.get("daemon_run_result")
    if isinstance(run_result, dict):
        st.caption(
            f"Last manual run: cycle={run_result.get('cycle_id', '')} "
            f"status={run_result.get('status', '')} "
            f"triggers={run_result.get('alerts_triggered', 0)}"
        )

    steps = status_payload.get("latest_cycle_steps", [])
    if isinstance(steps, list) and steps:
        st.markdown("Latest daemon steps")
        st.code("\n".join([str(item) for item in steps]), language="text")

    rules_payload, rules_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/rules",
        params={"include_inactive": False},
        timeout=30.0,
    )
    if rules_error:
        st.error(rules_error)
    elif isinstance(rules_payload, list):
        st.session_state.daemon_rules_payload = rules_payload
        st.markdown("##### Rule Catalog")
        st.dataframe(pd.DataFrame(rules_payload), width="stretch")

    cycles_payload, cycles_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/cycles",
        params={"limit": 60},
        timeout=30.0,
    )
    if cycles_error:
        st.error(cycles_error)
    elif isinstance(cycles_payload, list):
        st.session_state.daemon_cycles_payload = cycles_payload
        st.markdown("##### Daemon Cycles")
        cycles_frame = pd.DataFrame(cycles_payload)
        if not cycles_frame.empty and "steps" in cycles_frame.columns:
            cycles_frame = cycles_frame.drop(columns=["steps"])
        st.dataframe(cycles_frame, width="stretch")

    st.markdown("##### Trigger Logs")
    tf1, tf2, tf3 = st.columns([2, 2, 1])
    with tf1:
        trigger_symbol_filter = st.text_input(
            "Ticker Filter",
            value=str(st.session_state.get("admin_trigger_symbol_filter", "")),
            placeholder="AAPL, BTC...",
        ).strip()
    with tf2:
        trigger_user_filter_raw = st.text_input(
            "User ID Filter",
            value=str(st.session_state.get("admin_trigger_user_filter", "")),
            placeholder="e.g. 2",
        ).strip()
    with tf3:
        trigger_limit = int(
            st.number_input(
                "Rows",
                min_value=20,
                max_value=1000,
                value=200,
                step=20,
            )
        )

    st.session_state.admin_trigger_symbol_filter = trigger_symbol_filter
    st.session_state.admin_trigger_user_filter = trigger_user_filter_raw
    trigger_user_filter: int | None = None
    if trigger_user_filter_raw:
        try:
            trigger_user_filter = int(trigger_user_filter_raw)
        except ValueError:
            st.warning("User ID filter must be numeric; ignoring it.")

    trigger_params: dict[str, Any] = {"limit": trigger_limit}
    if trigger_symbol_filter:
        trigger_params["symbol"] = trigger_symbol_filter.upper()
    if trigger_user_filter is not None:
        trigger_params["user_id"] = trigger_user_filter

    triggers_payload, triggers_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/triggers",
        params=trigger_params,
        timeout=30.0,
    )
    if triggers_error:
        st.error(triggers_error)
    elif isinstance(triggers_payload, list):
        st.session_state.daemon_triggers_payload = triggers_payload
        st.dataframe(pd.DataFrame(triggers_payload), width="stretch")

    snapshots_payload, snapshots_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/snapshots",
        params={"limit": 240},
        timeout=45.0,
    )
    if snapshots_error:
        st.error(snapshots_error)
    elif isinstance(snapshots_payload, list):
        st.session_state.daemon_snapshots_payload = snapshots_payload
        st.markdown("##### Analysis Snapshots (DuckDB)")
        st.dataframe(pd.DataFrame(snapshots_payload), width="stretch")


def render_admin_logs() -> None:
    st.markdown("#### System Logs")
    level = st.selectbox(
        "Log Level Filter",
        ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        index=0,
        width="stretch",
    )
    limit = st.number_input("Tail Lines", min_value=20, max_value=5000, value=300, step=20)
    request_signature = f"{level}:{int(limit)}"
    if st.button("Refresh Logs", width="stretch"):
        st.session_state.admin_logs_payload = None
        st.session_state.admin_logs_signature = ""

    if st.session_state.get("admin_logs_signature", "") != request_signature:
        st.session_state.admin_logs_payload = None

    if st.session_state.get("admin_logs_payload") is None:
        payload, error, _ = admin_request(
            "GET",
            "/admin/logs",
            params={"level": level, "limit": int(limit)},
            timeout=30.0,
        )
        if error:
            st.error(error)
            return
        st.session_state.admin_logs_payload = payload
        st.session_state.admin_logs_signature = request_signature

    payload = st.session_state.get("admin_logs_payload")
    if not isinstance(payload, dict):
        st.info("No log payload available.")
        return

    st.caption(
        f"Configured level={payload.get('configured_level', 'INFO')} | "
        f"Filter={payload.get('active_level_filter', 'ALL')} | "
        f"Returned={payload.get('returned_count', 0)}"
    )
    st.caption(f"File: {payload.get('log_file_path', '')}")
    lines = payload.get("lines", [])
    if isinstance(lines, list) and lines:
        st.code("\n".join([str(line) for line in lines]), language="text")
    else:
        st.info("No log lines available for the selected filter.")


def render_alerts_page(symbol: str, asset_type: str) -> None:
    st.markdown("### Alert Subscriptions")
    if not str(st.session_state.get("admin_token", "")).strip():
        render_admin_login()
        return

    role = str(st.session_state.get("admin_role", "user")).lower()
    subscription_active = bool(st.session_state.get("admin_subscription_active", False))
    top_col1, top_col2 = st.columns([4, 1])
    with top_col1:
        st.caption(
            f"User `{st.session_state.get('admin_username', '')}` | role={role} | "
            f"subscription_active={subscription_active}"
        )
    with top_col2:
        if st.button("Logout", key="alerts_logout_btn", width="stretch"):
            admin_request("POST", "/admin/auth/logout")
            st.session_state.admin_token = ""
            st.session_state.admin_username = ""
            st.session_state.admin_role = ""
            st.session_state.admin_email = ""
            st.session_state.admin_subscription_ends_at = ""
            st.session_state.admin_subscription_active = False
            st.session_state.admin_alerts_enabled = False
            st.session_state.admin_mobile_phone = ""
            st.session_state.admin_logs_payload = None
            st.session_state.admin_logs_signature = ""
            st.session_state.admin_runtime_config = None
            st.session_state.admin_model_catalog = None
            st.session_state.admin_probe_result = None
            st.session_state.admin_selected_divergence_mode = "aggressive"
            st.session_state.daemon_status_payload = None
            st.session_state.daemon_cycles_payload = None
            st.session_state.daemon_triggers_payload = None
            st.session_state.daemon_rules_payload = None
            st.session_state.daemon_snapshots_payload = None
            st.session_state.daemon_run_result = None
            st.session_state.admin_trigger_symbol_filter = ""
            st.session_state.admin_trigger_user_filter = ""
            st.rerun()

    if role != "admin" and not subscription_active:
        st.error("Alerts section requires admin role or an active subscription.")
        return

    daemon_status, daemon_status_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/status",
        timeout=30.0,
    )
    if daemon_status_error:
        st.error(daemon_status_error)
    elif isinstance(daemon_status, dict):
        st.markdown("#### Alert Engine Status")
        d1, d2, d3 = st.columns(3)
        d1.metric("Daemon", "UP" if bool(daemon_status.get("is_running")) else "DOWN")
        d2.metric("Frequency (sec)", int(daemon_status.get("frequency_seconds", 0)))
        d3.metric("Triggered Alerts", int(daemon_status.get("triggered_count", 0)))
        st.caption(
            f"Cron hint: {daemon_status.get('cron_hint', '')} | "
            f"Last cycle: {daemon_status.get('latest_cycle_id', 'n/a')} | "
            f"Next run: {daemon_status.get('next_run_at', 'n/a')}"
        )
        if role == "admin":
            if st.button("Run Alert Cycle Now", key="alerts_manual_run", width="stretch"):
                _, run_error, _ = admin_request(
                    "POST",
                    "/admin/alerts/daemon/run",
                    json_data={"trigger_source": "manual"},
                    timeout=120.0,
                )
                if run_error:
                    st.error(run_error)
                else:
                    st.success("Alert cycle executed.")
                    st.rerun()

    rules_payload, rules_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/rules",
        params={"include_inactive": False},
        timeout=30.0,
    )
    rule_options = ["custom_threshold"]
    if rules_error:
        st.error(rules_error)
    elif isinstance(rules_payload, list):
        for item in rules_payload:
            if not isinstance(item, dict):
                continue
            key = str(item.get("rule_key", "")).strip()
            if key:
                rule_options.append(key)
        st.markdown("#### Available Alert Rules")
        st.dataframe(pd.DataFrame(rules_payload), width="stretch")

    trigger_payload, trigger_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/triggers",
        params={"limit": 120},
        timeout=30.0,
    )
    if trigger_error:
        st.error(trigger_error)
    elif isinstance(trigger_payload, list):
        st.markdown("#### Recent Trigger Logs")
        st.dataframe(pd.DataFrame(trigger_payload), width="stretch")

    cycles_payload, cycles_error, _ = admin_request(
        "GET",
        "/admin/alerts/daemon/cycles",
        params={"limit": 40},
        timeout=30.0,
    )
    if cycles_error:
        st.error(cycles_error)
    elif isinstance(cycles_payload, list):
        st.markdown("#### Daemon Cycles & Steps")
        cycles_frame = pd.DataFrame(cycles_payload)
        if not cycles_frame.empty and "steps" in cycles_frame.columns:
            st.dataframe(cycles_frame.drop(columns=["steps"]), width="stretch")
            cycle_options = {
                str(item.get("cycle_id", "")): item
                for item in cycles_payload
                if isinstance(item, dict)
            }
            if cycle_options:
                selected_cycle = st.selectbox(
                    "Inspect cycle steps",
                    options=list(cycle_options.keys()),
                    width="stretch",
                )
                selected_cycle_payload = cycle_options[selected_cycle]
                step_rows = selected_cycle_payload.get("steps", [])
                if isinstance(step_rows, list) and step_rows:
                    st.code("\n".join([str(step) for step in step_rows]), language="text")
        else:
            st.dataframe(cycles_frame, width="stretch")

    mine_only = True
    if role == "admin":
        mine_only = st.checkbox("Show only my subscriptions", value=True)

    payload, error, _ = admin_request(
        "GET",
        "/admin/alerts/subscriptions",
        params={"mine_only": mine_only},
    )
    subscriptions: list[dict[str, Any]] = []
    if error:
        st.error(error)
    elif isinstance(payload, list):
        subscriptions = [item for item in payload if isinstance(item, dict)]

    if subscriptions:
        st.dataframe(pd.DataFrame(subscriptions), width="stretch")
    else:
        st.info("No alert subscriptions found yet.")

    with st.form("create_alert_subscription_form"):
        st.markdown("Create Alert Subscription")
        form_symbol = st.text_input("Symbol", value=symbol)
        form_asset_type = st.selectbox(
            "Asset Type",
            ASSET_TYPES,
            index=ASSET_TYPES.index(asset_type),
        )
        form_scope = st.selectbox("Alert Scope", ["technical", "fundamental", "news", "agent"])
        selected_rule_key = st.selectbox(
            "Rule Template",
            options=rule_options,
            index=0,
            width="stretch",
        )
        metric_options = list(dict.fromkeys(SNAPSHOT_METRICS + ["news_sentiment", "agent_review"]))
        form_metric = st.selectbox("Metric", metric_options, index=0, width="stretch")
        form_operator = st.selectbox(
            "Operator",
            [">=", "<=", ">", "<", "==", "!="],
            width="stretch",
        )
        form_threshold = st.number_input("Threshold", value=0.0)
        form_frequency_seconds = int(
            st.number_input(
                "Run Frequency (seconds)",
                min_value=60,
                max_value=86400,
                value=3600,
                step=60,
            )
        )
        form_timeframe = st.selectbox(
            "Timeframe",
            ALERT_TIMEFRAMES,
            index=ALERT_TIMEFRAMES.index("1d"),
            width="stretch",
        )
        form_lookback = st.selectbox(
            "Lookback Period",
            SNAPSHOT_PERIODS,
            index=SNAPSHOT_PERIODS.index("6mo"),
            width="stretch",
        )
        form_cooldown = int(
            st.number_input(
                "Trigger Cooldown (minutes)",
                min_value=0,
                max_value=10080,
                value=60,
                step=5,
            )
        )
        form_notes = st.text_input("Notes")
        form_active = st.checkbox("Active", value=True)
        form_submit = st.form_submit_button("Create Subscription", width="stretch")
    if form_submit:
        metric_value = form_metric
        threshold_value = float(form_threshold)
        operator_value = form_operator
        rule_key_payload: str | None = None
        if selected_rule_key != "custom_threshold":
            rule_key_payload = selected_rule_key
            metric_value = "rule_trigger"
            operator_value = ">="
            threshold_value = 1.0
        create_payload, create_error, _ = admin_request(
            "POST",
            "/admin/alerts/subscriptions",
            json_data={
                "symbol": form_symbol.strip().upper(),
                "asset_type": form_asset_type,
                "alert_scope": form_scope,
                "rule_key": rule_key_payload,
                "metric": metric_value,
                "operator": operator_value,
                "threshold": threshold_value,
                "frequency_seconds": form_frequency_seconds,
                "timeframe": form_timeframe,
                "lookback_period": form_lookback,
                "cooldown_minutes": form_cooldown,
                "notes": form_notes.strip() or None,
                "is_active": form_active,
            },
        )
        if create_error:
            st.error(create_error)
        else:
            st.success(f"Subscription created: {create_payload.get('id', '')}")
            st.rerun()

    if not subscriptions:
        return

    st.markdown("Update / Delete Subscription")
    options = {
        (
            f"{item.get('id')} | {item.get('symbol')} | {item.get('metric')} | "
            f"user={item.get('username')}"
        ): item
        for item in subscriptions
    }
    selected_label = st.selectbox("Select Subscription", list(options.keys()), width="stretch")
    selected = options[selected_label]
    with st.form("update_alert_subscription_form"):
        scope_options = ["technical", "fundamental", "news", "agent"]
        selected_scope = str(selected.get("alert_scope", "technical"))
        if selected_scope not in scope_options:
            selected_scope = "technical"
        up_scope = st.selectbox(
            "Scope",
            scope_options,
            index=scope_options.index(selected_scope),
        )
        up_metric = st.text_input("Metric", value=str(selected.get("metric", "")))
        current_rule_key = str(selected.get("rule_key", "") or "")
        up_rule_key = st.selectbox(
            "Rule Template",
            options=rule_options,
            index=(
                rule_options.index(current_rule_key)
                if current_rule_key in rule_options
                else 0
            ),
            width="stretch",
        )
        operator_options = [">=", "<=", ">", "<", "==", "!="]
        selected_operator = str(selected.get("operator", ">="))
        if selected_operator not in operator_options:
            selected_operator = ">="
        up_operator = st.selectbox(
            "Operator",
            operator_options,
            index=operator_options.index(selected_operator),
        )
        up_threshold = st.number_input(
            "Threshold",
            value=_safe_float(selected.get("threshold", 0.0)),
        )
        up_frequency_seconds = int(
            st.number_input(
                "Run Frequency (seconds)",
                min_value=60,
                max_value=86400,
                value=int(selected.get("frequency_seconds", 3600)),
                step=60,
            )
        )
        selected_timeframe = str(selected.get("timeframe", "1d")).lower()
        if selected_timeframe not in ALERT_TIMEFRAMES:
            selected_timeframe = "1d"
        up_timeframe = st.selectbox(
            "Timeframe",
            ALERT_TIMEFRAMES,
            index=ALERT_TIMEFRAMES.index(selected_timeframe),
            width="stretch",
        )
        selected_lookback = str(selected.get("lookback_period", "6mo")).lower()
        if selected_lookback not in SNAPSHOT_PERIODS:
            selected_lookback = "6mo"
        up_lookback = st.selectbox(
            "Lookback Period",
            SNAPSHOT_PERIODS,
            index=SNAPSHOT_PERIODS.index(selected_lookback),
            width="stretch",
        )
        up_cooldown = int(
            st.number_input(
                "Trigger Cooldown (minutes)",
                min_value=0,
                max_value=10080,
                value=int(selected.get("cooldown_minutes", 60)),
                step=5,
            )
        )
        up_notes = st.text_input("Notes", value=str(selected.get("notes", "") or ""))
        up_active = st.checkbox("Active", value=bool(selected.get("is_active", True)))
        up_submit = st.form_submit_button("Update Subscription", width="stretch")
    if up_submit:
        up_metric_value = up_metric.strip().lower()
        up_operator_value = up_operator
        up_threshold_value = float(up_threshold)
        up_rule_payload: str | None = None
        if up_rule_key != "custom_threshold":
            up_rule_payload = up_rule_key
            up_metric_value = "rule_trigger"
            up_operator_value = ">="
            up_threshold_value = 1.0
        _, update_error, _ = admin_request(
            "PATCH",
            f"/admin/alerts/subscriptions/{selected.get('id')}",
            json_data={
                "alert_scope": up_scope,
                "rule_key": up_rule_payload,
                "metric": up_metric_value,
                "operator": up_operator_value,
                "threshold": up_threshold_value,
                "frequency_seconds": up_frequency_seconds,
                "timeframe": up_timeframe,
                "lookback_period": up_lookback,
                "cooldown_minutes": up_cooldown,
                "notes": up_notes.strip() or None,
                "is_active": up_active,
            },
        )
        if update_error:
            st.error(update_error)
        else:
            st.success("Subscription updated.")
            st.rerun()

    if st.button("Delete Selected Subscription", width="stretch"):
        _, delete_error, _ = admin_request(
            "DELETE",
            f"/admin/alerts/subscriptions/{selected.get('id')}",
        )
        if delete_error:
            st.error(delete_error)
        else:
            st.success("Subscription deleted.")
            st.rerun()


def render_admin_page(symbol: str, asset_type: str) -> None:
    st.markdown("### Admin Console")
    if not str(st.session_state.get("admin_token", "")).strip():
        render_admin_login()
        return

    if str(st.session_state.get("admin_role", "user")).lower() != "admin":
        st.warning("This workspace is restricted to admin users.")
        st.caption("Use the Alerts workspace for subscription management.")
        return

    top_col1, top_col2 = st.columns([4, 1])
    with top_col1:
        st.caption(
            f"Logged in as `{st.session_state.admin_username}` "
            f"({st.session_state.get('admin_email', '')})"
        )
    with top_col2:
        if st.button("Logout", key="admin_logout_btn", width="stretch"):
            admin_request("POST", "/admin/auth/logout")
            st.session_state.admin_token = ""
            st.session_state.admin_username = ""
            st.session_state.admin_role = ""
            st.session_state.admin_email = ""
            st.session_state.admin_subscription_ends_at = ""
            st.session_state.admin_subscription_active = False
            st.session_state.admin_alerts_enabled = False
            st.session_state.admin_mobile_phone = ""
            st.session_state.admin_logs_payload = None
            st.session_state.admin_logs_signature = ""
            st.session_state.admin_runtime_config = None
            st.session_state.admin_model_catalog = None
            st.session_state.admin_probe_result = None
            st.session_state.admin_selected_divergence_mode = "aggressive"
            st.session_state.daemon_status_payload = None
            st.session_state.daemon_cycles_payload = None
            st.session_state.daemon_triggers_payload = None
            st.session_state.daemon_rules_payload = None
            st.session_state.daemon_snapshots_payload = None
            st.session_state.daemon_run_result = None
            st.session_state.admin_trigger_symbol_filter = ""
            st.session_state.admin_trigger_user_filter = ""
            st.rerun()

    tabs = st.tabs(["Settings", "Diagnostics", "Alert Daemon", "Logs", "DB Query", "Users"])
    with tabs[0]:
        render_admin_settings(symbol=symbol, asset_type=asset_type)
    with tabs[1]:
        render_admin_diagnostics(symbol=symbol, asset_type=asset_type)
    with tabs[2]:
        render_admin_alert_daemon()
    with tabs[3]:
        render_admin_logs()
    with tabs[4]:
        render_admin_data_query()
    with tabs[5]:
        render_admin_users()


def main() -> None:
    st.set_page_config(page_title="Financial Recommender", layout="wide")
    init_state()
    render_base_css(theme_mode=str(st.session_state.ui_theme_mode))

    system_info = fetch_system_info()
    render_top_banner(system_info)

    sidebar_state = render_sidebar()
    symbol = str(sidebar_state["symbol"])
    asset_type = str(sidebar_state["asset_type"])

    section = str(sidebar_state["section"])
    if section == "Admin":
        render_admin_page(symbol=symbol, asset_type=asset_type)
    elif section == "Alerts":
        render_alerts_page(symbol=symbol, asset_type=asset_type)
    else:
        render_chat_page(symbol=symbol, asset_type=asset_type)


if __name__ == "__main__":
    main()

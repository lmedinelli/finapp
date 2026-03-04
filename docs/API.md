# API Reference

Base URL: `http://localhost:8000/v1`

## Public endpoints

### `GET /health`
Returns service liveness.

### `GET /system/info`
Returns app metadata (`app`, `version`, `env`, `author_name`, `author_url`, `timestamp`).

### `POST /market/ingest/{symbol}`
Ingests market data into DuckDB.
- Query: `asset_type=stock|crypto|etf`

### `GET /market/symbol-search`
Returns symbol autocomplete suggestions by ticker or name.
- Query params:
  - `q` (optional): search text. Empty query returns default catalog slice.
  - `limit` (optional): max suggestions (default `12`).
- Each result includes: `symbol`, `name`, `asset_type`.

### `GET /market/snapshot/{symbol}`
Computes configurable market metrics from yFinance data.
- Query params:
  - `asset_type=stock|crypto|etf`
  - `period` (for example `5d`, `1mo`, `6mo`, `1y`)
  - `interval` (for example `5m`, `15m`, `30m`, `60m`, `1d`, `1wk`)
  - `metrics` comma-separated list:
    - `latest_close`
    - `latest_open`, `latest_high`, `latest_low`
    - `market_cap`
    - `sma_15`, `sma_20`, `sma_30`, `sma_50`
    - `sma_100`, `sma_200`
    - `ema_15`, `ema_30`, `ema_50`, `ema_100`, `ema_200`
    - `rsi_14`, `rsi_30`
    - `macd`, `macd_signal`
    - `volume`
    - `momentum_10`, `momentum_30`
    - `volatility_20`
    - `atr_14`
    - `vwma_20`
    - `bb_upper_20`, `bb_lower_20`, `bb_percent_b_20`
    - `adx_14`
    - `obv`
    - `mfi_14`
    - `stoch_k_14`, `stoch_d_14`
    - `cci_20`
    - `williams_r_14`
    - `roc_10`
- Returns:
  - selected metric/value rows with `history` (last 5 consecutive periods)
  - per-metric `trend_status` (`improving|worsening|equal`) and `trend_delta`
  - `history_labels` for grouped chart legend
  - sample size and last timestamp
  - available metric list

### `GET /market/candle-image/{symbol}`
Returns TradingView-style candle image payload from Chart-IMG.
- Query params:
  - `asset_type=stock|crypto|etf`
  - `interval` (for example `1D`, `1W`, `1h`, `15m`)
  - `theme=light|dark`
  - `width`, `height`
  - `studies` comma-separated metrics/studies (for example `sma_20,ema_50,macd,volume,rsi_14`)
  - `exchange` (optional, resolver override)
- Returns:
  - `tradingview_symbol`
  - requested/applied studies
  - `content_type`
  - `image_base64`

Implementation note:
- Chart rendering uses Chart-IMG `v2` advanced-chart endpoint.
- Runtime is locked to Chart-IMG `v2` (v1/v3 are not used by the app flow).
- Default render size is `800x600`; backend auto-retries with account limit when provider returns a resolution-limit error.

### `GET /analysis/{symbol}`
Computes technical indicators from local timeseries data.
- Query: `asset_type=stock|crypto|etf` (used for symbol normalization)
- Uses ingest fallback when needed.

### `GET /news/{symbol}`
Returns headline list plus sentiment summary.
- Query: `asset_type=stock|crypto|etf`
- Uses SerpAPI when configured.

### `GET /market/alphavantage/context/{symbol}`
Returns AlphaVantage MCP bundle:
- `GLOBAL_QUOTE`
- `TIME_SERIES_DAILY` candles
- `NEWS_SENTIMENT` items
- derived trend summary
- local DuckDB candle fallback when AlphaVantage candles are unavailable
- Query: `asset_type=stock|crypto|etf`

### `GET /integrations/status`
Returns integration semaphores for:
- Timeseries DuckDB
- Admin SQLite DB
- SerpAPI
- AlphaVantage MCP
- AlphaVantage REST
- Chart-IMG
- CoinMarketCap
- OpenAI
- Alert Daemon
- MCP config presence

Includes runtime detail for:
- OpenAI current configured model
- Chart-IMG current API version and enforced limits (`daily`, `rate/sec`, `max_studies`, `max_resolution`, remaining quota from local tracker)

### `POST /recommendations`
Request body:
```json
{
  "symbol": "AAPL",
  "risk_profile": "balanced",
  "asset_type": "stock",
  "include_news": true
}
```
Returns short/long horizon actions, confidence, rationale, analysis snapshot, and news sentiment.

### `POST /chat`
Request body:
```json
{
  "message": "Should I buy AAPL short and long term?",
  "session_id": "optional-session-id",
  "symbol": "AAPL",
  "asset_type": "stock",
  "risk_profile": "balanced",
  "include_news": true,
  "include_alpha_context": true,
  "include_merged_news_sentiment": true
}
```
Returns:
- natural-language `answer`
- resolved `symbol` and `asset_type`
- structured `analysis`, `recommendation`, `news`, `market_context`
- optional `market_scan` block when message triggers ScanTheMarket workflow
- `workflow_steps` (agentic trace)
- reusable `session_id` for short-term memory

Chat scan trigger examples:
- `Scan the market for low cap gems including IPO and ICO signals`
- `Please ScanTheMarket for future stocks and crypto`

### `POST /scan/the-market`
Runs low-cap discovery workflow across stocks and crypto.

Body:
```json
{
  "low_cap_max_usd": 2000000000,
  "stock_limit": 8,
  "crypto_limit": 8,
  "include_ipo": true,
  "include_ico": true,
  "include_news": true,
  "exchanges": ["NASDAQ", "NYSE", "AMEX"]
}
```

Returns:
- ranked low-cap stock opportunities
- ranked low-cap crypto opportunities
- IPO and ICO watchlists
- news signals
- market scan id and timestamp
- source list and warnings

### `POST /portfolio/positions`
Creates a position in admin DB.

### `GET /portfolio/{user_id}/positions`
Lists positions for one user.

## Admin authentication endpoints

### `POST /admin/auth/login`
Creates admin session token.
```json
{
  "username": "admin",
  "password": "passw0rd"
}
```
Response also includes `role`, `email`, `subscription_ends_at`, and `subscription_active`.

### `POST /admin/auth/logout`
Revokes current session token (Bearer token required).

## Admin protected endpoints

All endpoints below require:
`Authorization: Bearer <token>`

### `GET /admin/db/summary`
Returns:
- SQLite admin table row counts
- DuckDB prices row/symbol counts
- latest timeseries timestamp

### `POST /admin/tests/run`
Runs backend pytest suites from API.

Body:
```json
{
  "suite": "smoke"
}
```

Supported suites:
- `smoke`
- `unit`
- `integration`
- `all`

### `POST /admin/db/query`
Executes read-only SQL against selected local DB.

Body:
```json
{
  "target_db": "timeseries",
  "sql": "SELECT symbol, timestamp, close FROM prices ORDER BY timestamp DESC",
  "limit": 100
}
```

Rules:
- only `SELECT` / `WITH`
- no write/DDL statements
- single statement only

### `GET /admin/db/tables`
Returns available table names for `target_db=admin|timeseries`.

### `GET /admin/logs`
Reads application log file for admin diagnostics.

Query:
- `level=ALL|DEBUG|INFO|WARNING|ERROR|CRITICAL`
- `limit` (10-5000)

Response includes:
- `configured_level` (from `.env` `LOG_LEVEL`)
- `active_level_filter`
- `log_file_path`
- `line_count`, `returned_count`
- `lines`

### `GET /admin/runtime/config`
Returns current runtime control values used by the running backend:
- `openai_model`
- `openai_model_candidates`
- `alert_divergence_15m_mode` (`conservative|balanced|aggressive`)
- `chart_img_api_version` (`v2`)
- Chart-IMG limits (`max_width`, `max_height`, `max_studies`, `rate_limit_per_sec`, `daily_limit`, `enforce_limits`)
- local usage stats (`chart_img_calls_today`, `chart_img_remaining_today`)

### `POST /admin/runtime/config`
Updates runtime controls without restarting the API.

Body example:
```json
{
  "openai_model": "gpt-5",
  "alert_divergence_15m_mode": "aggressive",
  "chart_img_api_version": "v2",
  "chart_img_max_width": 800,
  "chart_img_max_height": 600,
  "chart_img_max_studies": 3,
  "chart_img_rate_limit_per_sec": 1.0,
  "chart_img_daily_limit": 50,
  "chart_img_enforce_limits": true
}
```

### `GET /admin/openai/models`
Lists model ids visible to the configured OpenAI key and merges admin candidate models.

### `POST /admin/openai/probe`
Probes one selected OpenAI model.

Body example:
```json
{
  "model": "gpt-5"
}
```

### `POST /admin/chart-img/probe`
Probes Chart-IMG render with current runtime limits and selected API version.

Body example:
```json
{
  "symbol": "AAPL",
  "asset_type": "stock",
  "interval": "1D"
}
```

### `GET /admin/users`
Lists admin users.

### `POST /admin/users`
Creates user account (admin or subscribed user).
```json
{
  "username": "ops",
  "email": "ops@example.com",
  "mobile_phone": "+15551234567",
  "password": "secure-pass",
  "role": "admin",
  "subscription_ends_at": "2026-12-31T23:59:59",
  "alerts_enabled": true,
  "is_active": true
}
```

### `PATCH /admin/users/{user_id}`
Updates user (`email`, `mobile_phone`, `password`, `role`, `subscription_ends_at`, `alerts_enabled`, `is_active`).

### `DELETE /admin/users/{user_id}`
Deletes admin user with guard rails:
- cannot delete your current authenticated user
- cannot delete the last active admin user

## Alerts endpoints (admin or subscribed users)

All endpoints below require:
`Authorization: Bearer <token>`
with `role=admin` or `subscription_active=true`.

### `GET /admin/alerts/subscriptions`
List alert subscriptions. Query:
- `mine_only=true|false` (`false` available only for admin role).

### `POST /admin/alerts/subscriptions`
Create ticker alert subscription.
```json
{
  "symbol": "AAPL",
  "asset_type": "stock",
  "alert_scope": "technical",
  "rule_key": "buy_ema9_ema21_cross_with_rsi",
  "metric": "rsi_14",
  "operator": "<=",
  "threshold": 30.0,
  "frequency_seconds": 3600,
  "timeframe": "15m",
  "lookback_period": "6mo",
  "cooldown_minutes": 60,
  "notes": "Oversold alert",
  "is_active": true
}
```

### `PATCH /admin/alerts/subscriptions/{subscription_id}`
Update an alert subscription.

### `DELETE /admin/alerts/subscriptions/{subscription_id}`
Delete an alert subscription.

## Alert Daemon endpoints

### `GET /admin/alerts/daemon/status`
Returns scheduler/process status:
- running/enabled flags
- frequency and cron hint
- heartbeat and cycle timestamps
- latest cycle id and step list
- counters (`run_count`, `triggered_count`, `analyzed_count`)

### `POST /admin/alerts/daemon/run`
Runs one immediate daemon cycle (admin only).
```json
{
  "trigger_source": "manual"
}
```

### `POST /admin/alerts/daemon/start`
Starts background daemon loop in API process (admin only).

### `POST /admin/alerts/daemon/stop`
Stops background daemon loop in API process (admin only).

### `GET /admin/alerts/daemon/rules`
Lists alert rule catalog entries.

### `GET /admin/alerts/daemon/cycles`
Lists daemon cycles with counters and step logs.

### `GET /admin/alerts/daemon/triggers`
Lists persisted trigger events.
- Query:
  - `cycle_id` (optional)
  - `symbol` (optional)
  - `user_id` (optional, admin-only; non-admin is forced to own user id)
  - `limit` (default 200)

### `GET /admin/alerts/daemon/snapshots`
Lists analyzed metric rows from DuckDB `alert_analysis_snapshots`.
- Query: `cycle_id` (optional), `symbol` (optional), `limit`.

### `GET /admin/alerts/daemon/agent-feed`
Authenticated feed of daemon events for admin/alerts workspace.
- Query: `after_id`, `limit`.

### `GET /alerts/agent-feed`
Public read feed for chat proactive assistant events.
- Query: `after_id`, `limit`.

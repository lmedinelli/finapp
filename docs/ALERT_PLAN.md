# Alert Plan

## Objective
Create a deterministic alert engine that runs on a schedule, evaluates technical conditions for BUY/SELL opportunities, stores all analyzed data for auditability, and exposes full operational visibility in Admin/Alerts workspaces.

## Data Sources Used
- Local OHLCV via yFinance ingestion (`prices` in DuckDB).
- Technical metrics derived from local timeseries (no external dependency during rule evaluation).
- Existing recommendation/news context remains available as future signal inputs.

## Rule Catalog (Technical Analysis)
Rules are stored in `alert_rules` and evaluated in priority order.

### BUY-oriented rules
1. `buy_ema9_ema21_cross_with_rsi`
- EMA9 crosses above EMA21
- RSI14 <= 65
- MACD > MACD signal

2. `buy_sma20_sma50_golden_short`
- SMA20 crosses above SMA50
- Momentum30d > 0

3. `buy_macd_cross_with_volume`
- MACD crosses up
- Volume > 20-day average volume

4. `buy_rsi_oversold_reversion`
- RSI14 <= 30
- MACD slope positive (`macd_delta > 0`)

5. `buy_longterm_golden_50_200`
- SMA50 crosses above SMA200
- Momentum90d > 0

6. `buy_bullish_rsi_divergence`
- Price lower low + RSI higher low

7. `buy_bullish_macd_divergence`
- Price lower low + MACD higher low

### SELL-oriented rules
1. `sell_ema9_ema21_cross_with_rsi`
- EMA9 crosses below EMA21
- RSI14 >= 35
- MACD < MACD signal

2. `sell_sma20_sma50_death_short`
- SMA20 crosses below SMA50
- Momentum30d < 0

3. `sell_macd_cross_with_volume`
- MACD crosses down
- Volume > 20-day average volume

4. `sell_rsi_overbought_reversion`
- RSI14 >= 70
- MACD slope negative (`macd_delta < 0`)

5. `sell_longterm_death_50_200`
- SMA50 crosses below SMA200
- Momentum90d < 0

6. `sell_bearish_rsi_divergence`
- Price higher high + RSI lower high

7. `sell_bearish_macd_divergence`
- Price higher high + MACD lower high

## Subscription Rules
User subscriptions (`alert_subscriptions`) support:
- `rule_key` (template-based trigger) or custom threshold trigger (`metric`, `operator`, `threshold`)
- `frequency_seconds` (per-subscription check cadence)
- `timeframe` (`15m`, `1h`, `4h`, `1d`, `1wk`)
- `lookback_period` (`5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`)
- `cooldown_minutes` (trigger suppression window)

## 15m Divergence Sensitivity Tuning
- Env: `ALERT_DIVERGENCE_15M_MODE`
- Allowed values:
  - `conservative`: fewer triggers, stricter divergence thresholds.
  - `balanced` (default): medium trigger density.
  - `aggressive`: earlier/more frequent divergence triggers.
- The mode affects pivot window size, required price/oscillator separation, and recency constraints for divergence signals.

## Daemon Execution Pipeline
1. Load active subscriptions and active rule templates.
2. Build symbol target list (subscriptions first, fallback watchlist if empty).
3. Pull history and compute metric set.
4. Persist analyzed metric rows into DuckDB `alert_analysis_snapshots`.
5. Evaluate global rule catalog and user subscriptions.
6. Persist trigger logs and cycle summary.
7. Publish agent feed events for proactive chat.
8. Update daemon state/heartbeat/next run.

## Scheduling
- Configurable frequency: `ALERT_DAEMON_FREQUENCY_SECONDS` (default `3600`).
- Enable/disable:
  - `ALERT_DAEMON_ENABLED=true|false`
  - `ALERT_DAEMON_AUTOSTART=true|false` for API-process autostart.
- Optional process mode:
  - `make run-alert-daemon`
- Cron mode (hourly run-once):
  - `0 * * * * cd /path/to/repo && ./.venv/bin/python scripts/run_alert_cycle.py >> data/logs/alert_daemon_cron.log 2>&1`

## Monitoring and Observability
- Integration semaphore includes `alert_daemon` up/warn/down.
- Admin/Alerts UI shows:
  - daemon status
  - cron hint
  - run controls (start/stop/manual run)
  - cycle table + step logs
  - trigger log table
  - analyzed snapshot table
- System logs available via `GET /admin/logs` with `LOG_LEVEL` filtering.

## Persistence Model
- SQLite (`admin.db`):
  - `alert_rules`
  - `alert_daemon_state`
  - `alert_daemon_cycles`
  - `alert_trigger_logs`
  - `alert_agent_events`
  - extended `alert_subscriptions`
- DuckDB (`market.duckdb`):
  - `alert_analysis_snapshots`

## Proactive Chat Integration
- Daemon writes cycle summaries and trigger messages into `alert_agent_events`.
- Chat UI polls `/alerts/agent-feed` and appends new daemon messages automatically to conversation history.

## Future Extensions
- Twilio delivery worker can consume `alert_trigger_logs` rows with `delivered=false`.
- Add fundamental/news/agent composite rules in `alert_rules.expression_json`.
- Add confidence scoring and portfolio-aware position sizing.

## User Seed Workflow
- `make seed-alerts-lmedinelli`
- Builds and persists 20 stocks + 20 crypto subscriptions for `lmedinelli` (news-ranked + weekly-volume-ranked, with deterministic fallback lists) across `15m`, `1d`, and `1wk`.

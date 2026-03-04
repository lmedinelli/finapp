# Runbook

## Bootstrapping
```bash
./scripts/bootstrap.sh
```

## Start services
```bash
make run-api
make run-frontend
```

For stable backend logs without reload restarts:
```bash
make run-api-no-reload
```

## Seed admin data
```bash
make seed
```

## Ingest symbol
```bash
make ingest
python scripts/ingest_prices.py BTC-USD --asset-type crypto
```

## Chat workflow
1. Start API and frontend.
2. In sidebar `Workspace`, choose `Chat`.
3. Use `Search Symbol or Name` combo to pick ticker/name suggestion.
4. Confirm `Asset Type` (auto-applied from selection when available).
5. Use prompt shortcuts or ask a direct question like:
   - `Should I buy AAPL short term?`
   - `Long-term outlook for BTC?`
   - `Show me a candle image for NVDA with SMA, EMA, RSI and MACD`
   - `ScanTheMarket: scan stocks and crypto with CoinMarketCap + IPO/ICO + news signals`
6. Reuse `session_id` in `/v1/chat` requests to keep short memory context.

## Admin workflow
1. In sidebar `Workspace`, choose `Admin`.
2. Login with local admin credentials:
   - username from `BOOTSTRAP_ADMIN_USERNAME` (default `admin`)
   - password from `BOOTSTRAP_ADMIN_PASSWORD`
   - if password is unset, check backend logs for generated one-time credential in `APP_ENV=dev`
3. In `Settings` tab:
   - configure risk profile
   - toggle SerpAPI and AlphaVantage context
   - toggle merged sentiment mode (`NEWS_SENTIMENT` + SerpAPI)
   - select snapshot period/interval/metrics
   - run `Ingest / Refresh Market Data`
4. In Chat workspace `Market Snapshot`:
   - bars show 5 consecutive periods for each selected metric
   - metric trend color: green (improving), red (worsening), yellow (stable)
   - values are normalized for visibility; use table for raw values
   - Chart-IMG candle image is rendered automatically using selected snapshot metrics
5. In `Diagnostics` tab:
   - review integration semaphores
   - adjust runtime controls (OpenAI model + 15m divergence sensitivity + Chart-IMG limits)
   - run OpenAI model probe and Chart-IMG probe
   - run API probe
6. In `DB Query` tab:
   - run read-only SQL (`SELECT`/`WITH`) against `admin` or `timeseries`
7. In `Users` tab:
   - create/update/delete users with `email`, `role`, and `subscription_ends_at`
8. In `Logs` tab:
   - inspect full application logs from `LOG_FILE_PATH`
   - apply server-side level filter (`ALL`, `INFO`, `WARNING`, etc.)
9. In sidebar `Workspace`, choose `Alerts`:
   - available to `admin` users and `user` role with active subscription
   - create/update/delete ticker alert subscriptions for technical/fundamental/news/agent scopes
   - choose `rule_key` template or custom threshold metric
   - configure `frequency_seconds`, `lookback_period`, and `cooldown_minutes`
   - inspect daemon status, trigger logs, and cycle step traces
10. Trigger backend suites from `Run Backend Tests`:
   - `smoke`
   - `unit`
   - `integration`
   - `all`

## SerpAPI validation
1. Configure `SERPAPI_API_KEY` in `.env`.
2. Run script-level check:
   - `python scripts/test_serpapi.py AAPL --asset-type stock --limit 5 --debug`
   - or `make test-serpapi`
3. Run endpoint check:
   - `curl "http://localhost:8000/v1/news/AAPL?asset_type=stock"`
4. Run automated checks:
   - `pytest tests/unit/test_news.py tests/unit/test_news_fetch.py tests/integration/test_news_api.py`
   - `RUN_LIVE_SERPAPI_TESTS=1 pytest tests/integration/test_serpapi_live.py` (live only)

## AlphaVantage MCP validation
1. Configure `ALPHAVANTAGE_API_KEY` in `.env`.
2. Run context endpoint:
   - `curl "http://localhost:8000/v1/market/alphavantage/context/AAPL?asset_type=stock"`
3. Verify response includes:
   - `quote` from `GLOBAL_QUOTE`
   - `candles` from `TIME_SERIES_DAILY`
   - `news` from `NEWS_SENTIMENT`
   - derived `trend`

## Admin API auth validation
1. Login:
   - `curl -X POST http://localhost:8000/v1/admin/auth/login -H "Content-Type: application/json" -d "{\"username\":\"${BOOTSTRAP_ADMIN_USERNAME:-admin}\",\"password\":\"${BOOTSTRAP_ADMIN_PASSWORD:-change-me}\"}"`
2. Use returned token:
   - `curl http://localhost:8000/v1/admin/db/summary -H "Authorization: Bearer <token>"`
3. Logout:
   - `curl -X POST http://localhost:8000/v1/admin/auth/logout -H "Authorization: Bearer <token>"`

## Chart-IMG candle validation
1. Configure `CHART_IMG_API_KEY` in `.env`.
2. Confirm endpoint path is set (v2 render):
   - `CHART_IMG_BASE_URL=https://api.chart-img.com`
   - `CHART_IMG_ADVANCED_CHART_PATH=/v2/tradingview/advanced-chart`
3. Call endpoint:
   - `curl "http://localhost:8000/v1/market/candle-image/AAPL?asset_type=stock&interval=1D&studies=sma_20,ema_50,macd,volume,rsi_14"`
4. Run direct provider diagnostics:
   - `make test-chart-img-curl`
   - if it exits with code `2`, provider quota/rate limit blocked validation (`fatal external flow`)
5. Verify response has:
   - `tradingview_symbol`
   - `studies_applied`
   - `content_type`
   - non-empty `image_base64`
6. Run live test (optional):
   - `RUN_LIVE_CHART_IMG_TESTS=1 pytest tests/integration/test_chart_img_live.py`
7. Validate generated artifacts:
   - `tmp/chart_img/v2-advanced-x-api-key.png`
   - `tmp/chart_img/v2-advanced-storage-x-api-key.json`
8. Runtime controls endpoint checks:
   - `curl http://localhost:8000/v1/admin/runtime/config -H "Authorization: Bearer <token>"`
   - `curl -X POST http://localhost:8000/v1/admin/openai/probe -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"model":"gpt-5"}'`
   - `curl -X POST http://localhost:8000/v1/admin/chart-img/probe -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"symbol":"AAPL","asset_type":"stock","interval":"1D"}'`

## ScanTheMarket validation
1. Configure `COINMARKETCAP_API_KEY` in `.env` (recommended primary crypto source).
2. Run scan endpoint:
   - `curl -X POST http://localhost:8000/v1/scan/the-market -H "Content-Type: application/json" -d '{"low_cap_max_usd":2000000000,"stock_limit":8,"crypto_limit":8,"include_ipo":true,"include_ico":true,"include_news":true}'`
3. Verify payload sections:
   - `scan_id`
   - `generated_at`
   - `stock_opportunities`
   - `crypto_opportunities`
   - `ipo_watchlist`
   - `ico_watchlist`
   - `news_signals`
4. Trigger through chat:
   - `ScanTheMarket: scan stocks and crypto with CoinMarketCap + IPO/ICO + news signals`

## Alert daemon validation
1. Configure `.env`:
   - `ALERT_DAEMON_ENABLED=true`
   - `ALERT_DAEMON_FREQUENCY_SECONDS=3600`
   - `ALERT_DAEMON_AUTOSTART=false` (set `true` if you want API process autostart)
   - `ALERT_DIVERGENCE_15M_MODE=balanced` (`conservative` for less noise, `aggressive` for more signals)
2. Run one manual cycle:
   - `make run-alert-cycle`
   - default behavior includes pre-cycle daily data warmup for active subscription symbols.
   - to skip warmup: `PYTHONPATH=. .venv/bin/python scripts/run_alert_cycle.py --skip-warmup`
3. Run continuous process mode:
   - `make run-alert-daemon`
4. Optional cron mode (hourly):
   - `0 * * * * cd /path/to/repo && ./.venv/bin/python scripts/run_alert_cycle.py >> data/logs/alert_daemon_cron.log 2>&1`
5. Validate API status:
   - `curl http://localhost:8000/v1/admin/alerts/daemon/status -H "Authorization: Bearer <token>"`
6. Run cycle from API:
   - `curl -X POST http://localhost:8000/v1/admin/alerts/daemon/run -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"trigger_source":"manual"}'`
7. Validate persisted outputs:
   - `curl http://localhost:8000/v1/admin/alerts/daemon/cycles -H "Authorization: Bearer <token>"`
   - `curl http://localhost:8000/v1/admin/alerts/daemon/triggers -H "Authorization: Bearer <token>"`
   - `curl "http://localhost:8000/v1/admin/alerts/daemon/triggers?symbol=AAPL&limit=50" -H "Authorization: Bearer <token>"`
   - `curl http://localhost:8000/v1/admin/alerts/daemon/snapshots -H "Authorization: Bearer <token>"`
8. Validate proactive chat feed:
   - `curl "http://localhost:8000/v1/alerts/agent-feed?after_id=0&limit=20"`
9. Validate semaphore:
   - `curl http://localhost:8000/v1/integrations/status` and verify `alert_daemon` item.
10. Seed broad subscriptions for `lmedinelli`:
   - `make seed-alerts-lmedinelli`
   - seed now includes a bounded daily-history warmup pass and progress logging.

## Common issues
- Empty analysis response: ingest data first.
- API unreachable from Streamlit: verify API is running on port `8000`.
- No headlines in news output: verify `SERPAPI_API_KEY` is set and valid.
- `401` in admin endpoints: login expired or missing bearer token.
- Candle image unavailable: verify `CHART_IMG_API_KEY` and request interval/symbol format.
- Candle image is on-demand only from chat chart prompts (`candle`, `tradingview`, `diagram`); snapshot refresh does not call Chart-IMG.
- Candle image `403` with resolution-limit message: keep image size at `800x600` or lower for this key tier.
- Chart-IMG runtime is v2-only by policy in this app.
- Chart-IMG `429`/`Limit Exceeded`: reduce call volume, keep `1/sec`, and wait for daily quota reset.
- Alert daemon stays `DOWN`: verify `ALERT_DAEMON_ENABLED=true`, then run start/manual cycle.
- No triggers found: widen `lookback_period`, lower thresholds, or review active rule templates.
- `can't compare offset-naive and offset-aware datetimes`: fixed in daemon skip/cooldown normalization; rerun cycle after upgrading code.
- Repeated `no history for <symbol>` in cycle steps: run `make seed-alerts-lmedinelli` or `make run-alert-cycle` (warmup enabled) and verify market data provider/network access.

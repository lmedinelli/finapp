# Financial Recommender v0.2.0

Python-first platform for market data ingestion, analytics, and recommendation workflows across stocks, crypto, and ETFs.

## What is included
- FastAPI backend for ingestion, analytics, chat workflows, and recommendation APIs.
- Streamlit frontend (`Financial Recommender v0.2`) with three workspaces:
  - `Chat`: market snapshot (5 consecutive periods), Chart-IMG candle image, context/news panels, fixed-bottom prompt shortcuts + chat input, and scrollable conversation.
  - `Admin`: auth-protected controls for integrations, settings, DB diagnostics/query, test runner, and user CRUD.
  - `Alerts`: auth-protected ticker alert subscriptions for admin users and subscribed end users.
- Market snapshot supports 5-period grouped bars, trend-color status (green/red/yellow), and extended indicator catalog (SMA/EMA/RSI/MACD/ATR/ADX/OBV/MFI/Stochastic/Bollinger/VWMA/ROC/CCI/Williams %R + Market Cap).
- Candle image endpoint backed by Chart-IMG for TradingView-style chart snapshots with indicator overlays.
- `ScanTheMarket` workflow for low-cap stock/crypto opportunity scans with IPO/ICO/news context (CoinMarketCap + CoinGecko + yFinance + SerpAPI + AlphaVantage sentiment).
- Prompt shortcuts managed through `config/prompt_shortcuts.json` for easy future updates.
- SQLite local admin database for users and portfolio data.
- SQLite short-memory chat storage for conversational context.
- Recommendation and market scan event logging tables for adherence tracking.
- DuckDB local timeseries database for OHLCV data.
- MCP server exposing ingest, analytics, news, and recommendation tools.
- CI, linting, tests, Makefile, Docker, and project docs.

## Project structure
- `app/`: backend application code.
- `frontend/`: Streamlit end-user application.
- `config/`: app and MCP configuration.
- `scripts/`: bootstrap, seed, and ingestion scripts.
- `tests/`: unit and integration tests.
- `docs/`: architecture and operating documentation.
- `data/`: local databases and timeseries files.

## Quickstart
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
make seed
make run-api
```

Set optional AI/news keys in `.env` for full chat experience:
```bash
OPENAI_API_KEY=...
OPENAI_ADMIN_MODEL_CANDIDATES=gpt-5,gpt-5-mini,gpt-5.3-codex,gpt-4.1,gpt-4.1-mini,o3,o4-mini
SERPAPI_API_KEY=...
ALPHAVANTAGE_API_KEY=...
CHART_IMG_API_KEY=...
CHART_IMG_API_VERSION=v2
CHART_IMG_MAX_WIDTH=800
CHART_IMG_MAX_HEIGHT=600
CHART_IMG_MAX_STUDIES=3
CHART_IMG_RATE_LIMIT_PER_SEC=1
CHART_IMG_DAILY_LIMIT=50
CHART_IMG_ENFORCE_LIMITS=true
COINMARKETCAP_API_KEY=...
COINGECKO_API_KEY=...
```

In a second terminal:
```bash
source .venv/bin/activate
make run-frontend
```

Prompt shortcuts management:
```bash
cat config/prompt_shortcuts.json
```

Admin bootstrap credentials (local development):
- username: value of `BOOTSTRAP_ADMIN_USERNAME` (default `admin`)
- password: value of `BOOTSTRAP_ADMIN_PASSWORD` from your `.env`
- if `BOOTSTRAP_ADMIN_PASSWORD` is unset, a one-time password is generated on bootstrap (logged in backend logs for `APP_ENV=dev`)

System author metadata:
- Author: `Luis Medinelli`
- Site: `https://medinelli.ai`

After first login, change or rotate users in `Admin -> Users`.

## API examples
```bash
curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/system/info
curl "http://localhost:8000/v1/market/symbol-search?q=apple&limit=20"
curl -X POST "http://localhost:8000/v1/market/ingest/AAPL?asset_type=stock"
curl "http://localhost:8000/v1/market/snapshot/AAPL?asset_type=stock&period=6mo&interval=1d&metrics=latest_close,market_cap,sma_20,ema_50,rsi_14,macd,volume,adx_14,mfi_14,stoch_k_14"
curl "http://localhost:8000/v1/market/candle-image/AAPL?asset_type=stock&interval=1D&studies=sma_20,ema_50,macd,volume,rsi_14"
curl "http://localhost:8000/v1/analysis/AAPL?asset_type=stock"
curl http://localhost:8000/v1/news/AAPL
curl "http://localhost:8000/v1/market/alphavantage/context/AAPL?asset_type=stock"
curl -X POST http://localhost:8000/v1/scan/the-market \
  -H "Content-Type: application/json" \
  -d '{"low_cap_max_usd":2000000000,"stock_limit":8,"crypto_limit":8,"include_ipo":true,"include_ico":true,"include_news":true}'
curl http://localhost:8000/v1/integrations/status

# Admin login (capture token)
# Set BOOTSTRAP_ADMIN_PASSWORD in .env, or read the generated one-time password from backend logs (APP_ENV=dev)
ADMIN_PASSWORD="${BOOTSTRAP_ADMIN_PASSWORD:?BOOTSTRAP_ADMIN_PASSWORD must be set in .env}"
TOKEN=$(curl -s -X POST http://localhost:8000/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"$ADMIN_PASSWORD\"}" | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl http://localhost:8000/v1/admin/db/summary -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/v1/admin/runtime/config -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/v1/admin/runtime/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"openai_model":"gpt-5","chart_img_api_version":"v2","chart_img_max_width":800,"chart_img_max_height":600,"chart_img_max_studies":3,"chart_img_rate_limit_per_sec":1.0,"chart_img_daily_limit":50,"chart_img_enforce_limits":true}'
curl http://localhost:8000/v1/admin/openai/models -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/v1/admin/openai/probe \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5"}'
curl -X POST http://localhost:8000/v1/admin/chart-img/probe \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","asset_type":"stock","interval":"1D"}'
curl -X POST http://localhost:8000/v1/admin/tests/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"suite":"smoke"}'
curl -X POST http://localhost:8000/v1/admin/db/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_db":"timeseries","sql":"SELECT symbol, timestamp, close FROM prices ORDER BY timestamp DESC","limit":25}'
curl "http://localhost:8000/v1/admin/db/tables?target_db=admin" -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/v1/admin/alerts/subscriptions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","asset_type":"stock","alert_scope":"technical","metric":"rsi_14","operator":"<=","threshold":30.0,"is_active":true}'

curl -X POST http://localhost:8000/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","risk_profile":"balanced","asset_type":"stock","include_news":true}'
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Should I buy AAPL short and long term?","session_id":"demo-session","symbol":"AAPL","include_alpha_context":true,"include_merged_news_sentiment":true}'

# Agent scan trigger through chat
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Scan the market for low cap gems including IPO and ICO signals."}'
```

## SerpAPI test
Configure local key in `.env`:
```bash
SERPAPI_API_KEY=your_private_key
```

Run connectivity check:
```bash
python scripts/test_serpapi.py AAPL --asset-type stock --limit 5 --debug
```

Run live pytest (optional):
```bash
RUN_LIVE_SERPAPI_TESTS=1 pytest tests/integration/test_serpapi_live.py
```

Reference guide: `docs/SERPAPI_TESTING.md`.
Prompt guide: `docs/PROMPTS.md`.

## MCP server
Run MCP stocks server:
```bash
python -m app.mcp.server
```

Reference config: `config/mcp.stocks.json`.

## Quality gates
```bash
make lint
make typecheck
make test
make test-chart-img-curl
```

The Makefile auto-detects `.venv/bin/python` when available, so `make lint/typecheck/test/run-*` uses the project virtual environment by default.

## GitHub setup
1. Initialize local git repository:
   ```bash
   git init
   git add .
   git commit -m "chore: bootstrap financial recommender platform"
   ```
2. Create remote repository (GitHub CLI):
   ```bash
   gh repo create <your-org-or-user>/financial-recommender --private --source=. --push
   ```

## Notes
- Market data is sourced from `yfinance`.
- News context uses SerpAPI when `SERPAPI_API_KEY` is configured.
- OpenAI-backed chat generation uses `OPENAI_API_KEY` when configured.
- OpenAI generation uses `responses` first, with chat-completions fallback for compatibility.
- AlphaVantage MCP context uses `ALPHAVANTAGE_API_KEY` when configured.
- Chart image generation uses `CHART_IMG_API_KEY` when configured.
- Chart-IMG integration is pinned to v2 render endpoint only in this release.
- `ScanTheMarket` uses yFinance + CoinMarketCap + CoinGecko + SerpAPI + AlphaVantage sentiment.
- Admin API endpoints require Bearer auth from `/v1/admin/auth/login`.
- Recommendation output is decision support only, not financial advice.

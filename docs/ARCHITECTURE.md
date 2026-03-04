# Architecture

## Components
- Backend API (`FastAPI`): ingest, analytics, yFinance snapshot metrics, Chart-IMG candle rendering, news, AlphaVantage MCP context, ScanTheMarket, alert daemon/rules, chat recommendation, portfolio and admin APIs.
- Admin operations API: authentication, integration semaphores, diagnostics, read-only DB query, user management (`admin`/`user` + subscription), alert subscription CRUD, and controlled test execution.
- Admin diagnostics also includes server log access filtered by level (`LOG_LEVEL` / `LOG_FILE_PATH`).
- Symbol catalog API: autocomplete suggestions by symbol/name with asset-type metadata.
- Storage:
  - SQLite (`data/admin/admin.db`) for administrative entities.
  - SQLite `chat_memory` table for short-term conversational context.
  - SQLite logging tables for `recommendation_logs`, `market_scan_logs`, and alert daemon operational logs.
  - DuckDB (`data/timeseries/market.duckdb`) for OHLCV time series.
  - DuckDB `alert_analysis_snapshots` for daemon metric history.
- Frontend (`Streamlit`): `Chat`, `Admin`, and `Alerts` workspaces with top sticky banner (`Financial Recommender v0.2` + author metadata).
  - Chat workspace: market snapshot grouped chart (5 periods + trend colors), Chart-IMG candle snapshot, news/context panels, fixed-bottom prompt shortcuts/input, scrollable conversation panel.
    - Prompt shortcuts are managed in `config/prompt_shortcuts.json`.
  - Admin workspace (admin login required): strategy/snapshot controls, semaphores, runtime controls (OpenAI model + Chart-IMG version/limits), API probe, test runner, DB query, and user/admin CRUD.
  - Alerts workspace (admin or subscribed-user login): ticker alert subscriptions plus daemon status/rules/cycle logs.
- MCP server (`app/mcp/server.py`): exposes ingest/analysis/news/recommendation/chat tools plus AlphaVantage context.

## Layering
- `api`: HTTP interface and DTO mapping.
- `services`: domain logic for market data, analytics, news, AlphaVantage MCP, Chart-IMG, yFinance snapshots, ScanTheMarket, alert daemon/rule evaluation, recommendations, and agentic chat orchestration.
- `services/admin_auth.py`: admin login/session lifecycle and user credential management.
- `services/admin_tools.py`: admin diagnostics, read-only DB query, and pytest execution.
- `services/runtime_controls.py`: persistent runtime overrides and probes for OpenAI and Chart-IMG integrations.
- `services/symbol_catalog.py`: symbol/name search for UI autocomplete.
- `repositories`: database access for admin entities.
- `db`: low-level database connections/schemas.

## Agentic workflow
- Chat pipeline runs deterministic tools first (`analysis` + ingest fallback, `recommendation`, optional SerpAPI and AlphaVantage).
- Recommendation and scan outputs are persisted in SQLite for later adherence tracking.
- Optional merged sentiment mode combines SerpAPI and AlphaVantage `NEWS_SENTIMENT` outputs.
- Scan intent path (`ScanTheMarket` trigger text) runs low-cap stock/crypto scan using yFinance + CoinMarketCap (+CoinGecko fallback), IPO/ICO watchlist collection, and news signal aggregation.
- Alert daemon path evaluates template rules + user subscriptions on a configurable cadence (`ALERT_DAEMON_FREQUENCY_SECONDS`), logs each cycle, and emits proactive assistant events.
- Local short memory uses SQLite `chat_memory` table keyed by `session_id`.
- Optional OpenAI synthesis layer (`OPENAI_API_KEY`) generates user-facing final answer from tool context.

## Design goals
- Python-native, fast to iterate.
- Clear separation between admin metadata and timeseries workload.
- AI-ready via MCP and explicit docs/config.
- Recommendation output is explicitly decision support (non-advisory).
- OpenAI-backed response generation is optional and controlled via environment config.

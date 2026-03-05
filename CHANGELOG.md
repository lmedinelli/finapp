# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-03-02
### Added
- Initial project scaffold for financial recommendation and analysis.
- FastAPI backend, Streamlit frontend, SQLite and DuckDB storage.
- MCP server for stock ingestion and analysis.
- Tests, CI workflow, docs, and developer tooling.

## [0.2.1] - 2026-03-04
### Security
- Remove hard-coded bootstrap admin password (`passw0rd`); bootstrap credentials are now fully env-driven via `BOOTSTRAP_ADMIN_PASSWORD`, or a cryptographically random one-time password is generated on first boot (plaintext shown in logs only when `APP_ENV=dev`).

## [0.2.0] - 2026-03-03
### Added
- Chat-first end-user workflow (`POST /v1/chat`) and Streamlit chat interface.
- Expanded analytics with RSI, MACD, ATR, Bollinger bands, SMA-200, trend/support/resistance.
- News endpoint and SerpAPI integration with headline sentiment scoring.
- Short and long-horizon recommendation outputs and expanded MCP tools.
- CoinMarketCap integration for ScanTheMarket crypto discovery (with CoinGecko fallback).
- Chart-IMG candle endpoint integration coverage tests for render/search/exchanges/symbols.
- Alert subscription APIs for admin and active-subscriber users.
- Alert daemon subsystem: technical rule catalog, hourly scheduler, cycle/trigger logs, and proactive chat feed.
- Recommendation and market scan persistence logs in SQLite.
- Alert analysis snapshot persistence in DuckDB for historical analytics.
- Admin user schema extension: email, role, subscription end date.
- Streamlit UX updates: fixed-bottom prompt/input area, scrollable conversation pane, 5-period snapshot trend colors.
- System metadata update: `Financial Recommender v0.2.0`, author `Luis Medinelli`.

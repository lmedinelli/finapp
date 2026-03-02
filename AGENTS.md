# AGENTS

This file defines operational guidance for AI coding agents working on this repository.

## Mission
Build and maintain a production-ready financial recommendation and analytics platform for stocks, crypto, and ETFs.

## Architecture rules
- Keep Python as the primary language.
- Backend API belongs in `app/` (FastAPI).
- End-user frontend belongs in `frontend/` (Streamlit unless replaced intentionally).
- Administrative data must remain in SQLite (`data/admin/admin.db`).
- Timeseries data must remain in DuckDB (`data/timeseries/market.duckdb`) unless a migration is approved.
- MCP integration for market tooling must be maintained in `app/mcp/` and `config/mcp.stocks.json`.

## Coding standards
- Add/maintain type hints for public functions.
- Keep service logic pure where possible for testability.
- Add or update tests for behavior changes (`tests/unit`, `tests/integration`).
- Run `make lint`, `make typecheck`, and `make test` before proposing merges.

## Data and security
- Never commit secrets; use `.env` and `.env.example`.
- Treat recommendation output as decision support, not financial advice.
- Record assumptions in docs when adding risk models or scoring logic.

## Workflow
- For new features: update API docs and architecture notes in `docs/`.
- For schema changes: document data model updates in `docs/DATA_MODEL.md`.
- For new MCP tools: document usage in `docs/MCP.md` and add tests if feasible.

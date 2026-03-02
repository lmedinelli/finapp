# Architecture

## Components
- Backend API (`FastAPI`): ingest, analytics, recommendation, portfolio admin.
- Storage:
  - SQLite (`data/admin/admin.db`) for administrative entities.
  - DuckDB (`data/timeseries/market.duckdb`) for OHLCV time series.
- Frontend (`Streamlit`): user-facing dashboard calling backend APIs.
- MCP server (`app/mcp/server.py`): exposes ingest/analysis tools to AI clients.

## Layering
- `api`: HTTP interface and DTO mapping.
- `services`: domain logic for market data, analytics, recommendations.
- `repositories`: database access for admin entities.
- `db`: low-level database connections/schemas.

## Design goals
- Python-native, fast to iterate.
- Clear separation between admin metadata and timeseries workload.
- AI-ready via MCP and explicit docs/config.

# Data Model

## SQLite (`admin.db`)
- `user_profiles`
  - `id`, `name`, `risk_profile`, `base_currency`, `created_at`
- `portfolio_positions`
  - `id`, `user_id`, `symbol`, `asset_type`, `quantity`, `avg_price`, `updated_at`

## DuckDB (`market.duckdb`)
- `prices`
  - `symbol`, `asset_type`, `timestamp`, `open`, `high`, `low`, `close`, `volume`

## Storage strategy
- SQLite stores low-volume relational metadata.
- DuckDB stores columnar analytical timeseries.

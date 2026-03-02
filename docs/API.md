# API Reference

Base URL: `http://localhost:8000/v1`

## `GET /health`
Returns service status.

## `POST /market/ingest/{symbol}`
Ingests market data into local timeseries DB.
- Query: `asset_type=stock|crypto|etf`

## `GET /analysis/{symbol}`
Computes technical indicators from local timeseries store.

## `POST /recommendations`
Body:
```json
{
  "symbol": "AAPL",
  "risk_profile": "balanced",
  "asset_type": "stock"
}
```

## `POST /portfolio/positions`
Creates a position in admin DB.

## `GET /portfolio/{user_id}/positions`
Lists positions for one user.

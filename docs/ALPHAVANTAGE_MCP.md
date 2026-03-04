# AlphaVantage MCP Integration

This project integrates the AlphaVantage MCP endpoint as an external market context tool.

## Configuration
Set in `.env`:

```bash
ALPHAVANTAGE_MCP_URL=https://mcp.alphavantage.co/mcp
ALPHAVANTAGE_API_KEY=your_key
ALPHAVANTAGE_TIMEOUT_SECONDS=20
ALPHAVANTAGE_DAILY_POINTS=120
ALPHAVANTAGE_NEWS_ITEMS=10
```

## Functions used
- `GLOBAL_QUOTE`
- `TIME_SERIES_DAILY`
- `NEWS_SENTIMENT`

## Resilience behavior
- Primary source: AlphaVantage MCP URL (`ALPHAVANTAGE_MCP_URL`)
- Automatic fallback: official REST endpoint (`ALPHAVANTAGE_REST_URL`) when MCP payload is not data
- Common ticker typo normalization: `APPL -> AAPL`
- Flexible response parsing for alternate MCP payload key shapes
- API-level fallback to local DuckDB candles when AlphaVantage daily series is empty

## API endpoint
```bash
curl "http://localhost:8000/v1/market/alphavantage/context/AAPL?asset_type=stock"
```

Response includes:
- `quote`
- `candles`
- `news`
- derived `trend`
- `warnings` list with upstream/API errors or fallback messages

## Agent workflow usage
- `POST /v1/chat` accepts `include_alpha_context: true`
- response includes `market_context` and tool step trace in `workflow_steps`

## Tests
```bash
PYTHONPATH=. pytest tests/unit/test_alphavantage_mcp.py tests/integration/test_alphavantage_api.py
```

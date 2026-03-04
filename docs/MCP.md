# MCP Server

Entry point: `python -m app.mcp.server`

## Tools exposed
- `ingest_symbol(symbol, asset_type="stock")`
- `analyze_symbol(symbol, asset_type="stock")`
- `get_news(symbol, asset_type="stock")`
- `get_recommendation(symbol, risk_profile="balanced", asset_type="stock")`
- `chat_recommendation(message, symbol="", asset_type="stock", risk_profile="balanced", session_id="")`
- `alphavantage_market_context(symbol)`
- `scan_the_market(low_cap_max_usd=2000000000, stock_limit=8, crypto_limit=8)`

## Config
`config/mcp.stocks.json` is provided for MCP-compatible clients.

## Notes
- MCP tool output is deterministic and JSON-serializable.
- `SERPAPI_API_KEY` is optional and used only for the news-related tools.
- Keep keys in `.env` or client environment variables; do not hardcode secrets in tracked config files.
- `OPENAI_API_KEY` enables LLM response generation in chat tool outputs.
- `ALPHAVANTAGE_API_KEY` enables AlphaVantage MCP proxy tool outputs.
- `CHART_IMG_API_KEY` enables chart-img powered symbol discovery used by `scan_the_market`.
- `COINMARKETCAP_API_KEY` enables primary crypto scanning source for `scan_the_market`.
- `COINGECKO_API_KEY` is optional for higher-rate crypto scan requests.

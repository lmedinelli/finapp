# MCP Server

Entry point: `python -m app.mcp.server`

## Tools exposed
- `ingest_symbol(symbol, asset_type="stock")`
- `analyze_symbol(symbol)`

## Config
`config/mcp.stocks.json` is provided for MCP-compatible clients.

## Notes
- MCP tool output is deterministic and JSON-serializable.
- API keys are not required in baseline due to `yfinance` source.

# ScanTheMarket Guide

## Goal
`ScanTheMarket` finds potential low-cap opportunities in stocks and crypto, then enriches results with IPO/ICO and sentiment/news context.

Endpoint:
- `POST /v1/scan/the-market`

MCP tool:
- `scan_the_market(low_cap_max_usd, stock_limit, crypto_limit)`

Chat trigger:
- `ScanTheMarket: scan stocks and crypto with CoinMarketCap + IPO/ICO + news signals`

## Current data providers used
- `yfinance`: stock prices, volume, momentum, and market cap estimates.
- `CoinMarketCap`: primary low-cap and momentum crypto discovery.
- `CoinGecko`: fallback crypto discovery and trending context.
- `SerpAPI`: IPO/ICO and theme headline collection.
- `AlphaVantage NEWS_SENTIMENT`: sentiment enrichment for selected opportunities.
- `Chart-IMG` TradingView symbol endpoints: exchange/symbol discovery input for stock candidate universe.

## Suggested API keys
Configure in `.env`:
- `SERPAPI_API_KEY`
- `ALPHAVANTAGE_API_KEY`
- `CHART_IMG_API_KEY`
- `COINMARKETCAP_API_KEY`
- `COINGECKO_API_KEY` (optional for higher-rate plan)

Additional recommended keys for future expansion:
- `POLYGON_API_KEY` (IPO calendar and broader equities data)
- `FMP_API_KEY` (screener and corporate-event endpoints)
- `FINNHUB_API_KEY` (market news/filings/event coverage)

## Suggested query patterns

SerpAPI theme queries:
- `upcoming IPO this week US`
- `new crypto listing exchange`
- `small cap stocks unusual volume`
- `micro cap biotech catalyst`
- `AI infrastructure small cap breakout`

AlphaVantage sentiment topics:
- `ipo`
- `earnings`
- `mergers_and_acquisitions`
- `blockchain`
- `financial_markets`

## About StockAnalysis.com
Public support content indicates there is no official public API.  
Use it as a manual research surface, and rely on API-first providers for automated workflows.

## Response blocks
`ScanTheMarket` returns:
- `scan_id`
- `generated_at`
- `stock_opportunities`
- `crypto_opportunities`
- `ipo_watchlist`
- `ico_watchlist`
- `news_signals`
- `data_sources`
- `warnings`

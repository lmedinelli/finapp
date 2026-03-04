# Candle Image Integration (Chart-IMG)

Validated on: March 3, 2026.

## Summary
Chart image generation is now implemented with Chart-IMG as the rendering provider.

Implemented endpoint:
- `GET /v1/market/candle-image/{symbol}`

Service:
- `app/services/chart_img.py`

Frontend usage:
- Market Snapshot now auto-renders the candle image by default.
- Studies are derived from the metrics selected in Admin Snapshot settings.

## Chart-IMG account/API analysis

Reference docs and account API area:
- https://doc.chart-img.com/
- https://chart-img.com/account/api
- Tutorials index: https://doc.chart-img.com/#tutorials

Observed API model from official docs:
1. Auth:
   - request header: `x-api-key: <your_key>`
   - query fallback also accepted in current API: `?key=<your_key>`
2. Base URL:
   - `https://api.chart-img.com`
3. Candle render endpoint:
   - `POST /v2/tradingview/advanced-chart`
   - `POST /v2/tradingview/advanced-chart/storage` (returns URL JSON)
Tutorial alignment used in implementation:
- simple chart generation flow (base URL + API key header + symbol + interval)
- advanced chart with studies overlay payload

Notes:
- API key must be configured in `.env` (`CHART_IMG_API_KEY`), not hardcoded.
- `symbol` should be TradingView format (for example `NASDAQ:AAPL`, `BINANCE:BTCUSDT`).
- Rendering endpoint remains v2 for now (`/v2/tradingview/advanced-chart`).
- For this account, v2 enforces a resolution cap (`800x600`), so the backend now auto-falls back when a larger size is requested.
- Runtime policy is locked to v2 only in app flow.
- For Basic tier constraints, runtime limits are enforced in backend:
  - max resolution `800x600`
  - max studies/indicators `3`
  - rate limit `1/sec`
  - daily cap `50` requests (tracked locally in `chart_img_usage_log`)

## Current API contract

### `GET /v1/market/candle-image/{symbol}`
Query:
- `asset_type=stock|crypto|etf`
- `interval` (for example `1D`, `1W`, `1h`, `15m`)
- `theme=light|dark`
- `width`, `height`
- `studies` (csv metrics/studies, e.g. `sma_20,ema_50,macd,volume,rsi_14`)
- `exchange` (optional resolver override)

Response:
- `tradingview_symbol`
- `studies_requested`
- `studies_applied`
- `content_type`
- `image_base64`
- `source`

## Study mapping
Selected metrics are translated to Chart-IMG study names when possible:
- `sma_*` -> `Moving Average`
- `ema_*` -> `Moving Average Exponential`
- `rsi_*` -> `Relative Strength Index`
- `macd` / `macd_signal` -> `Moving Average Convergence Divergence`
- `volume` -> `Volume`
- `bb_*` -> `Bollinger Bands`
- `atr_14` -> `Average True Range`
- `adx_14` -> `Average Directional Index`
- `obv` -> `On Balance Volume`
- `mfi_14` -> `Money Flow Index`
- `stoch_*` -> `Stochastic`
- `cci_20` -> `Commodity Channel Index`
- `williams_r_14` -> `Williams %R`
- `roc_10` -> `Rate of Change`
- `vwma_20` -> `Volume Weighted Moving Average`

Study payload format:
- Use `input` for optional parameter overrides (not `inputs`).

## Validation checklist
1. Add key in `.env`:
   - `CHART_IMG_API_KEY=...`
2. Run API:
   - `make run-api-no-reload`
3. Run direct curl diagnostics:
   - `make test-chart-img-curl`
4. Call endpoint:
   - `curl "http://localhost:8000/v1/market/candle-image/AAPL?asset_type=stock&interval=1D&studies=sma_20,ema_50,macd,volume,rsi_14"`
5. Verify:
   - non-empty `image_base64`
   - expected `tradingview_symbol`
   - non-empty `studies_applied`

## Implemented function coverage
The service currently exercises all Chart-IMG functions used by the app:
- `render_candle_image` (v2 advanced chart rendering)

Automated tests:
- `tests/unit/test_chart_img.py`
- `scripts/test_chart_img_v1_v2_curl.sh`

## Next improvements
1. Add optional raw image passthrough endpoint for direct PNG streaming.
2. Add deterministic symbol routing table per exchange for equities and ETFs.
3. Add local render fallback (Plotly + kaleido) if external image provider fails.

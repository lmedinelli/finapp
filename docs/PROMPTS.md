# Prompt Catalog

Prompt shortcuts used in the Chat workspace are configured in:
- `config/prompt_shortcuts.json`

The frontend loads this file at runtime, so you can add, remove, or reorder prompts without editing code.

## Current prompts

1. `Should I buy AAPL for the next 2 weeks?`
2. `Long-term outlook for NVDA for 12 months.`
3. `Compare BTC and ETH for a balanced portfolio.`
4. `Where are the key support and resistance levels for SPY?`
5. `What are the major risk factors for TSLA right now?`
6. `Show me a candle image for NVDA with SMA, EMA, RSI and MACD.`
7. `ScanTheMarket: scan stocks and crypto with CoinMarketCap + IPO/ICO + news signals.`

## Prompt config format

```json
{
  "prompts": [
    {"text": "Prompt text...", "category": "optional-tag"},
    {"text": "Another prompt..."}
  ]
}
```

Notes:
- `text` is the only required field.
- If the file is missing or invalid, the app falls back to built-in defaults.

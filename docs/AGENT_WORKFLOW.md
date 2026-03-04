# Agent Workflow

The chat endpoint implements an agentic workflow with tool orchestration and short memory.

## Goals
- Keep a short local memory in SQLite.
- Run market tools in sequence (`analysis`, `ingest` if needed, `recommendation`, `news`, `alphavantage_context`).
- Optionally merge SerpAPI and AlphaVantage `NEWS_SENTIMENT` into one sentiment signal.
- Support `ScanTheMarket` intent path for low-cap discovery + IPO/ICO/news signals.
- Use OpenAI to synthesize a final user-facing response when configured, with model failover.
- Fall back to deterministic response generation if OpenAI is not configured.

## Memory model
- Database: `data/admin/admin.db`
- Table: `chat_memory`
- Fields: `session_id`, `role`, `content`, `created_at`
- Scope: short memory only (last `AGENT_MEMORY_MESSAGES` messages per session)

## Environment variables
- `OPENAI_API_KEY`: required for LLM response generation
- `OPENAI_MODEL`: default `gpt-4.1`
- `OPENAI_BASE_URL`: optional custom endpoint
- `OPENAI_ADMIN_MODEL_CANDIDATES`: CSV candidate list used as fallback model chain
- `AGENT_MEMORY_MESSAGES`: memory window size
- `ALPHAVANTAGE_API_KEY`: enables quote/time-series/news context via AlphaVantage MCP
- `ALPHAVANTAGE_MCP_URL`: default `https://mcp.alphavantage.co/mcp`

## API usage
Use `POST /v1/chat` with `session_id` to continue memory across turns:

```json
{
  "message": "Should I add BTC now?",
  "session_id": "user-123-session",
  "symbol": "BTC",
  "asset_type": "crypto",
  "risk_profile": "balanced",
  "include_news": true,
  "include_alpha_context": true,
  "include_merged_news_sentiment": true
}
```

Response includes:
- `session_id`
- `symbol` and `asset_type` resolved by the workflow
- `workflow_steps` (tool execution trace)
- structured `analysis`, `recommendation`, `news`

## LLM execution path
When OpenAI is enabled:
1. Build compact tool context JSON from analysis/recommendation/news/MCP outputs.
2. Try `responses` API with `OPENAI_MODEL`.
3. If unavailable/error/empty output, iterate fallback models from `OPENAI_ADMIN_MODEL_CANDIDATES`.
4. If Responses chain still fails, try `chat.completions` with a short fallback model subset.
5. If all LLM attempts fail, return deterministic local fallback answer.

`workflow_steps` emits model-specific traces, for example:
- `llm:responses_attempt:gpt-4.1`
- `llm:responses_success:gpt-4.1`
- `llm:responses_error:gpt-5.3-codex:BadRequestError`
- `llm:model_fallback:gpt-5.3-codex->gpt-4.1-mini`

## On-demand chart behavior
- Chart-IMG is not called during default snapshot refresh.
- Chart-IMG is called only when chat prompt includes chart intent keywords (`candle`, `tradingview`, `chart image`, etc.).
- This protects daily quota and rate limits while keeping chart generation available on demand.

## Scan trigger
Example message:
- `Scan the market for low cap gems including IPO and ICO signals`

Behavior:
- bypasses single-symbol analysis flow
- runs ScanTheMarket service
- returns `market_scan` payload in chat response

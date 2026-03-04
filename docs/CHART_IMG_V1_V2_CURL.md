# Chart-IMG V1/V2 Curl Validation

Validated: March 3, 2026.

References reviewed:
- https://chart-img.medium.com/tradingview-snapshot-with-rest-api-part1-74f4d8403015
- https://chart-img.medium.com/tradingview-snapshot-with-rest-api-part2-b200c7705dff
- https://doc.chart-img.com/

## Goal
Validate Chart-IMG endpoint behavior with direct `curl` against v2 and v1 routes, and document the production-safe path for this app.

## How to run
1. Ensure `.env` includes:
   - `CHART_IMG_API_KEY`
   - `CHART_IMG_BASE_URL=https://api.chart-img.com`
2. Run:
   - `make test-chart-img-curl`
   - optional dual-auth run: `CHART_IMG_TEST_AUTH_MODES="x-api-key query-key" make test-chart-img-curl`
3. Review generated artifacts:
   - `tmp/chart_img/v3-exchange-list.json`
   - `tmp/chart_img/v2-advanced-x-api-key.png`
   - `tmp/chart_img/v2-advanced-query-key.png`
   - `tmp/chart_img/v2-advanced-storage-*.json`

Exit codes:
- `0`: V2 image validation passed.
- `1`: V2 endpoint did not return an image.
- `2`: fatal external limit flow (provider rate/quota limit blocked validation).

## Current observed behavior
- `GET /v3/tradingview/exchange/list` -> `200` (works)
- `GET /v3/tradingview/exchange/{exchange}` -> `200` (works)
- `GET /v3/tradingview/search/{query}` -> may return `404` depending on account/rollout
- `POST /v2/tradingview/advanced-chart` -> `200` with PNG (works)
- `POST /v2/tradingview/advanced-chart/storage` -> `200` with JSON URL (works)
- `POST /v1/tradingview/advanced-chart` -> `404 Route Not Found`
- `POST /v1/tradingview/advanced-chart/storage` -> `404 Route Not Found`
- `POST /v1/tradingview/mini-chart` -> `404 Route Not Found`
- `POST /v1/tradingview/mini-chart/storage` -> `404 Route Not Found`

## Resolution limit finding
For this API key, requests larger than `800x600` return:
- `403` with message similar to `Exceed Max Usage Resolution Limit (800x600)`.

Application fix:
- Backend now retries automatically with the account limit if this error appears.
- API and frontend defaults were changed to `800x600` for stable behavior.

## Implementation decision
Treat v2 as authoritative runtime integration and keep v1 only as diagnostic reference.

Fatal flow criteria:
- If v2 endpoints return `404`/`410`, integration is blocked and the provider version/path must be revalidated.
- If v2 returns repeated auth errors (`401`/`403`) with both `x-api-key` and `?key=`, API key/account must be rechecked.

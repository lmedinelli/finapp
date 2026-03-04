# SerpAPI Testing Guide

This project supports SerpAPI for news retrieval used by recommendations and chat responses.

## 1) Configure key
Set `SERPAPI_API_KEY` in local `.env` (gitignored):

```bash
SERPAPI_API_KEY=your_private_key
```

## 2) Test direct service script
Run a direct connectivity and parsing check:

```bash
source .venv/bin/activate
python scripts/test_serpapi.py AAPL --asset-type stock --limit 5 --debug
```

Or with Make:

```bash
make test-serpapi
```

Expected output:
- JSON with `headlines_count`
- `sentiment` object (`score`, `label`, `sample_size`)
- list of normalized `headlines`
- if no headlines, debug fields (`debug_status_code`, `debug_payload`) help diagnose invalid key or quota issues

## 3) Test API endpoint
Start the API:

```bash
make run-api
```

Call the news endpoint:

```bash
curl "http://localhost:8000/v1/news/AAPL?asset_type=stock"
```

Expected output:
- `symbol`, `asset_type`
- `headlines` array
- `sentiment` object

## 4) Test with pytest
Offline/mocked tests:

```bash
pytest tests/unit/test_news.py tests/unit/test_news_fetch.py tests/integration/test_news_api.py
```

Live SerpAPI test (requires valid key):

```bash
RUN_LIVE_SERPAPI_TESTS=1 pytest tests/integration/test_serpapi_live.py
```

If `RUN_LIVE_SERPAPI_TESTS` or key is missing, live test is skipped automatically.

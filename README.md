# Financial Recommender

Python-first platform for market data ingestion, analytics, and recommendation workflows across stocks, crypto, and ETFs.

## What is included
- FastAPI backend for ingestion, analytics, portfolio admin, and recommendation APIs.
- Streamlit frontend dashboard for end-user interaction.
- SQLite local admin database for users and portfolio data.
- DuckDB local timeseries database for OHLCV data.
- MCP server for stock tooling integration with AI clients.
- CI, linting, tests, Makefile, Docker, and project docs.

## Project structure
- `app/`: backend application code.
- `frontend/`: Streamlit end-user application.
- `config/`: app and MCP configuration.
- `scripts/`: bootstrap, seed, and ingestion scripts.
- `tests/`: unit and integration tests.
- `docs/`: architecture and operating documentation.
- `data/`: local databases and timeseries files.

## Quickstart
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
make seed
make run-api
```

In a second terminal:
```bash
source .venv/bin/activate
make run-frontend
```

## API examples
```bash
curl http://localhost:8000/v1/health
curl -X POST "http://localhost:8000/v1/market/ingest/AAPL?asset_type=stock"
curl http://localhost:8000/v1/analysis/AAPL
curl -X POST http://localhost:8000/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","risk_profile":"balanced","asset_type":"stock"}'
```

## MCP server
Run MCP stocks server:
```bash
python -m app.mcp.server
```

Reference config: `config/mcp.stocks.json`.

## Quality gates
```bash
make lint
make typecheck
make test
```

## GitHub setup
1. Initialize local git repository:
   ```bash
   git init
   git add .
   git commit -m "chore: bootstrap financial recommender platform"
   ```
2. Create remote repository (GitHub CLI):
   ```bash
   gh repo create <your-org-or-user>/financial-recommender --private --source=. --push
   ```

## Notes
- This baseline uses `yfinance` for market data and rule-based recommendation logic.
- Replace recommendation engine with ML/LLM strategies incrementally.

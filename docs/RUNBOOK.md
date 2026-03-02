# Runbook

## Bootstrapping
```bash
./scripts/bootstrap.sh
```

## Start services
```bash
make run-api
make run-frontend
```

## Seed admin data
```bash
make seed
```

## Ingest symbol
```bash
make ingest
python scripts/ingest_prices.py BTC-USD --asset-type crypto
```

## Common issues
- Empty analysis response: ingest data first.
- API unreachable from Streamlit: verify API is running on port `8000`.

ifneq ($(wildcard .venv/bin/python),)
PYTHON ?= .venv/bin/python
else
PYTHON ?= python3
endif

.PHONY: install dev lint typecheck test run-api run-api-no-reload run-frontend run-alert-daemon run-alert-cycle seed seed-alerts-lmedinelli ingest test-serpapi test-chart-img-curl format clean

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy app

test:
	PYTHONPATH=. $(PYTHON) -m pytest

run-api:
	$(PYTHON) -m uvicorn app.main:app --reload \
		--reload-dir app \
		--reload-dir config \
		--reload-exclude ".venv/*" \
		--reload-exclude "tests/*" \
		--reload-exclude "frontend/*" \
		--host 0.0.0.0 --port 8000

run-api-no-reload:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

run-frontend:
	$(PYTHON) -m streamlit run frontend/streamlit_app.py --server.port 8501

run-alert-daemon:
	PYTHONPATH=. $(PYTHON) scripts/run_alert_daemon.py

run-alert-cycle:
	PYTHONPATH=. $(PYTHON) scripts/run_alert_cycle.py

seed:
	$(PYTHON) scripts/seed_demo_data.py

seed-alerts-lmedinelli:
	PYTHONPATH=. $(PYTHON) scripts/seed_alerts_lmedinelli.py --username lmedinelli --run-cycle

ingest:
	$(PYTHON) scripts/ingest_prices.py

test-serpapi:
	./.venv/bin/python scripts/test_serpapi.py AAPL --asset-type stock --limit 5 --debug

test-chart-img-curl:
	./scripts/test_chart_img_v1_v2_curl.sh

format:
	$(PYTHON) -m ruff check . --fix

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

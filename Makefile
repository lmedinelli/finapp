PYTHON ?= python3

.PHONY: install dev lint typecheck test run-api run-frontend seed ingest format clean

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e .[dev]

lint:
	ruff check .

typecheck:
	mypy app

test:
	pytest

run-api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	streamlit run frontend/streamlit_app.py --server.port 8501

seed:
	$(PYTHON) scripts/seed_demo_data.py

ingest:
	$(PYTHON) scripts/ingest_prices.py

format:
	ruff check . --fix

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

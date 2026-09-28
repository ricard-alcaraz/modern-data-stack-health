# --- Cross-platform virtualenv detection -------------------------------
# On Windows (cmd AND Git Bash/MSYS) $(OS) is "Windows_NT".
# On macOS/Linux it is unset or something else.
ifeq ($(OS),Windows_NT)
    VENV_PY  := .venv/Scripts/python
    VENV_DAGS := .venv/Scripts/dagster dev
else
    VENV_PY  := .venv/bin/python
    VENV_DAGS := .venv/bin/dagster dev
endif

.PHONY: setup ingest dbt-run dbt-docs dagster-up clean

setup:
	@echo "Setting up Python environment..."
	python -m venv .venv
	$(VENV_PY) -m pip install -r requirements.lock
	
ingest:
	@echo "Running data ingestion..."
	$(VENV_PY) -m ingestion.main

dbt-run:
	@echo "Running dbt build (via cross-platform wrapper)..."
	$(VENV_PY) -m transform.run_dbt build --target prod

dbt-docs:
	@echo "Generating and serving dbt docs..."
	$(VENV_PY) -m transform.run_dbt docs generate
	$(VENV_PY) -m transform.run_dbt docs serve

dagster-up:
	@echo "Starting Dagster UI..."
	$(VENV_DAGS) -m orchestration.modern_data_stack.definitions

test:
	@echo "Running pytest..."
	$(VENV_PY) -m pytest tests/

clean:
	@echo "Cleaning up local cache and landing data..."
	rm -rf data/landing/*
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.duckdb" -delete
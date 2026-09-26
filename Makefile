.PHONY: setup ingest dbt-run dbt-docs dagster-up clean

setup:
	@echo "Setting up Python environment..."
	python -m venv .venv
	.venv\Scripts\pip install -r ingestion/requirements.txt
	.venv\Scripts\pip install dbt-duckdb
	.venv\Scripts\pip install dagster==1.12.8 dagster-webserver==1.12.8 dagster-dbt==0.28.8 dagster-pipes==1.12.8

ingest:
	@echo "Running data ingestion..."
	.venv\Scripts\python -m ingestion.main

dbt-run:
	@echo "Running dbt build (via cross-platform wrapper)..."
	.venv\Scripts\python -m transform.run_dbt build

dbt-docs:
	@echo "Generating and serving dbt docs..."
	.venv\Scripts\python -m transform.run_dbt docs generate
	.venv\Scripts\python -m transform.run_dbt docs serve

dagster-up:
	@echo "Starting Dagster UI..."
	.venv\Scripts\dagster dev -m orchestration.modern_data_stack.definitions

clean:
	@echo "Cleaning up local cache and landing data..."
	rm -rf data/landing/*
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.duckdb" -delete
.PHONY: up down ingest transform dbt-run dbt-test ml pipeline logs test test-unit test-integration

up:
	docker compose up -d --build

down:
	docker compose down -v

ingest:
	docker compose run --rm ingestion

transform:
	docker compose run --rm transformer

dbt-run:
	docker compose run --rm dbt run

dbt-test:
	docker compose run --rm dbt test

ml:
	docker compose run --rm ml

pipeline: ingest transform dbt-run dbt-test ml
	@echo "Full pipeline completed successfully"

logs:
	docker compose logs -f

test-unit:
	pip install -q -r tests/requirements.txt -r transformations/requirements.txt && pytest tests/test_unit.py -v

test-integration:
	docker compose run --rm -e POSTGRES_HOST=postgres -e POSTGRES_DB=warehouse -e POSTGRES_USER=warehouse_user -e POSTGRES_PASSWORD=warehouse_pass -v "$(CURDIR)/tests:/tests" transformer bash -c "pip install -q pytest && python -m pytest /tests/test_integration.py -v"
test: test-unit

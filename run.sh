#!/usr/bin/env bash
# Health Data Platform - Bash runner (no Make required)
# Usage: ./run.sh up   |  ./run.sh pipeline  |  ./run.sh down

set -e
cd "$(dirname "$0")"

cmd="${1:-}"
case "$cmd" in
  up)
    docker compose up -d --build
    ;;
  down)
    docker compose down -v
    ;;
  ingest)
    docker compose run --rm ingestion
    ;;
  transform)
    docker compose run --rm transformer
    ;;
  dbt-run)
    docker compose run --rm dbt run
    ;;
  dbt-test)
    docker compose run --rm dbt test
    ;;
  ml)
    docker compose run --rm ml
    ;;
  test)
    docker compose run --rm test
    ;;
  logs)
    docker compose logs -f
    ;;
  pipeline)
    docker compose run --rm ingestion
    docker compose run --rm transformer
    docker compose run --rm dbt run
    docker compose run --rm dbt test
    docker compose run --rm ml
    echo "Full pipeline completed successfully"
    ;;
  *)
    echo "Usage: $0 {up|down|pipeline|ingest|transform|dbt-run|dbt-test|ml|test|logs}"
    exit 1
    ;;
esac

"""Integration test: verify data was loaded into the warehouse.
   Run after pipeline (e.g. inside Docker network where 'postgres' resolves)."""
import os
import psycopg2


def test_data_loaded_into_warehouse():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "warehouse"),
        user=os.getenv("POSTGRES_USER", "warehouse_user"),
        password=os.getenv("POSTGRES_PASSWORD", "warehouse_pass"),
    )

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM health_life_expectancy;")
    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    assert count > 0, "No data found in warehouse table"

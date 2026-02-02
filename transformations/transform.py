import os
import sys
import logging
import time
import json
import pandas as pd
from io import StringIO
from datetime import datetime
from minio import Minio
import psycopg2

# Force logs to appear immediately (no buffering when run in Docker)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ------------------------
# Logging
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

# ------------------------
# Config
# ------------------------
BUCKET_NAME = "raw-health-data"
DATASET_PREFIX = "who_life_expectancy"

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "warehouse")
POSTGRES_USER = os.getenv("POSTGRES_USER", "warehouse_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "warehouse_pass")
# Optional: set MAX_ROWS (e.g. 5000) for a quick run during development
MAX_ROWS = os.getenv("MAX_ROWS")

# ------------------------
# File format detection and loading
# ------------------------
# WHO GHO can be (1) CSV with columns SpatialDim, SpatialDimCode, TimeDim, Dim1, NumericValue
# or (2) OData JSON with "value": [ { SpatialDim, TimeDim, Dim1, NumericValue, ... } ]
# Dim1: CSV uses "Both sexes"; JSON uses "SEX_BTSX" (both), "SEX_FMLE", "SEX_MLE"
BOTH_SEXES_VALUES = ("Both sexes", "SEX_BTSX")


def _load_csv(path):
    """Load WHO CSV format."""
    return pd.read_csv(path)


def _load_json(path):
    """Load WHO OData JSON format (e.g. life_expectancy.csv in parent folder)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("value", data)
    if not rows:
        raise ValueError("JSON has no 'value' array or it is empty")
    # Normalize to same column names as CSV for rest of pipeline
    df = pd.DataFrame(rows)
    # JSON has SpatialDim (code) but no SpatialDimCode column; use SpatialDim for both
    if "SpatialDimCode" not in df.columns:
        df["SpatialDimCode"] = df["SpatialDim"].astype(str)
    if "SpatialDim" not in df.columns and "SpatialDimCode" in df.columns:
        df["SpatialDim"] = df["SpatialDimCode"]
    return df


def load_raw_file(path):
    """Detect JSON vs CSV and return DataFrame with columns: SpatialDim, SpatialDimCode, TimeDim, Dim1, NumericValue."""
    with open(path, "rb") as f:
        peek = f.read(50).decode("utf-8", errors="ignore").strip()
    if peek.startswith("{"):
        logger.info("Detected OData JSON format")
        return _load_json(path)
    logger.info("Detected CSV format")
    return _load_csv(path)


# ------------------------
# Data Quality Checks
# ------------------------
def validate_data(df):
    logging.info("Running data quality checks")

    # Null check
    if df["NumericValue"].isnull().any():
        raise ValueError("Null values found in life expectancy")

    # Duplicate check (SpatialDimCode = SpatialDim in JSON)
    key_cols = ["SpatialDimCode", "TimeDim", "Dim1"]
    if not all(c in df.columns for c in key_cols):
        key_cols = [c for c in key_cols if c in df.columns]
    duplicates = df.duplicated(subset=key_cols).sum()
    if duplicates > 0:
        raise ValueError(f"Duplicate rows detected: {duplicates}")

    logging.info("Data quality checks passed")


# ------------------------
# Main Logic
# ------------------------
def main():
    t_start = time.perf_counter()
    logger.info("Starting transformation job")
    sys.stdout.flush()

    # --- Step 1: Connect to MinIO and find latest file ---
    t0 = time.perf_counter()
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    objects = list(client.list_objects(BUCKET_NAME, prefix=DATASET_PREFIX, recursive=True))
    latest_object = sorted(objects, key=lambda o: o.last_modified)[-1]
    logger.info(f"MinIO: found {len(objects)} object(s) in {time.perf_counter() - t0:.1f}s — using {latest_object.object_name}")

    # --- Step 2: Download to temp file then read (JSON or CSV; format auto-detected) ---
    t0 = time.perf_counter()
    ext = ".json" if latest_object.object_name.endswith(".json") else ".csv"
    local_path = f"/tmp/life_expectancy_raw{ext}"
    logger.info("Downloading raw data from MinIO...")
    sys.stdout.flush()
    client.fget_object(BUCKET_NAME, latest_object.object_name, local_path)
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    logger.info(f"Downloaded {size_mb:.1f} MB in {time.perf_counter() - t0:.1f}s, parsing...")
    sys.stdout.flush()
    t_parse = time.perf_counter()
    df = load_raw_file(local_path)
    logger.info(f"Parsed {len(df)} rows in {time.perf_counter() - t_parse:.1f}s")

    # --- Step 3: Filter (both sexes only) and validate ---
    t0 = time.perf_counter()
    # CSV uses "Both sexes", OData JSON uses "SEX_BTSX"
    df = df[df["Dim1"].isin(BOTH_SEXES_VALUES)].copy()
    if df.empty:
        raise ValueError("No rows left after filtering for both sexes (Dim1 in %s)" % (BOTH_SEXES_VALUES,))
    if MAX_ROWS:
        df = df.head(int(MAX_ROWS))
        logger.info(f"Limited to {len(df)} rows (MAX_ROWS={MAX_ROWS})")
    validate_data(df)
    logger.info(f"Filter + validation: {len(df)} rows, {time.perf_counter() - t0:.1f}s")

    # --- Step 4: Normalize schema ---
    t0 = time.perf_counter()
    clean_df = pd.DataFrame({
        "country_name": df["SpatialDim"],
        "country_code": df["SpatialDimCode"],
        "year": df["TimeDim"].astype(int),
        "sex": df["Dim1"],
        "life_expectancy": df["NumericValue"].astype(float),
        "ingested_at": datetime.utcnow(),
    })
    logger.info(f"Normalized schema: {len(clean_df)} rows in {time.perf_counter() - t0:.1f}s")

    # --- Step 5: Load to PostgreSQL via COPY (much faster than INSERT) ---
    t0 = time.perf_counter()
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    cur = conn.cursor()

    # COPY is 5–20x faster than batched INSERT
    buffer = StringIO()
    clean_df.to_csv(
        buffer,
        index=False,
        header=False,
        date_format="%Y-%m-%d %H:%M:%S",
        float_format="%.4f",
    )
    buffer.seek(0)
    cur.copy_expert(
        """COPY health_life_expectancy (country_name, country_code, year, sex, life_expectancy, ingested_at)
           FROM STDIN WITH (FORMAT csv)""",
        buffer,
    )
    conn.commit()
    cur.close()
    conn.close()

    total = len(clean_df)
    elapsed = time.perf_counter() - t0
    logger.info(f"PostgreSQL COPY: {total} rows in {elapsed:.1f}s ({total / max(elapsed, 0.01):.0f} rows/s)")
    logger.info(f"Transformation completed successfully in {time.perf_counter() - t_start:.1f}s total")


if __name__ == "__main__":
    main()

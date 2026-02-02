import os
import sys
import logging
import requests
from datetime import datetime
from minio import Minio

# ------------------------
# Logging configuration
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

# ------------------------
# Config
# ------------------------
# WHO GHO OData API: default response is JSON (value array); no ?format=csv
WHO_URL = "https://ghoapi.azureedge.net/api/WHOSIS_000001"
BUCKET_NAME = "raw-health-data"
DATASET_NAME = "who_life_expectancy"

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# ------------------------
# Main logic
# ------------------------
def main():
    ingestion_date = datetime.utcnow().strftime("%Y-%m-%d")
    object_path = f"{DATASET_NAME}/ingestion_date={ingestion_date}/life_expectancy.json"

    logging.info("Starting WHO GHO data ingestion (JSON)")

    # Download JSON (OData format: { "value": [ ... ] }); store raw bytes (no parse in ingestion)
    response = requests.get(WHO_URL)
    response.raise_for_status()
    size_mb = len(response.content) / (1024 * 1024)
    logging.info("Downloaded WHO life expectancy JSON (%.2f MB)", size_mb)

    local_file = "/tmp/life_expectancy.json"
    with open(local_file, "wb") as f:
        f.write(response.content)

    # Connect to MinIO
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    # Create bucket if not exists
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        logging.info("Created bucket: %s", BUCKET_NAME)

    # Upload to MinIO
    client.fput_object(
        BUCKET_NAME,
        object_path,
        local_file,
        content_type="application/json",
    )

    logging.info("Uploaded raw JSON to MinIO: %s", object_path)
    logging.info("Ingestion completed successfully")


if __name__ == "__main__":
    main()

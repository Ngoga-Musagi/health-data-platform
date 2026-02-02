import os
import sys
import time
import logging
import warnings

# Suppress warnings before importing mlflow/sklearn
warnings.filterwarnings("ignore", message=".*Git.*")
warnings.filterwarnings("ignore", message=".*artifact_path.*")
warnings.filterwarnings("ignore", message=".*pickle or cloudpickle.*")
warnings.filterwarnings("ignore", message=".*inferring pip requirements.*")

import pandas as pd
import mlflow
import mlflow.sklearn
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

# Reduce MLflow env inference noise
logging.getLogger("mlflow").setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "warehouse")
POSTGRES_USER = os.getenv("POSTGRES_USER", "warehouse_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "warehouse_pass")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
EXPERIMENT_NAME = "life_expectancy_prediction"

DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/{POSTGRES_DB}"
)


def wait_for_mlflow(max_wait_sec=120):
    import urllib.request
    import urllib.error
    base = MLFLOW_TRACKING_URI.rstrip("/")
    url = f"{base}/health" if not base.endswith("/health") else base
    start = time.time()
    while time.time() - start < max_wait_sec:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except (OSError, urllib.error.URLError):
            logging.warning("MLflow not ready yet, retrying in 5s...")
            time.sleep(5)
    raise RuntimeError(
        "MLflow did not become ready in time. Run: docker compose up -d and wait ~30s before ./run.sh ml"
    )


def load_data():
    query = """
        SELECT country_code, year, avg_life_expectancy
        FROM mart_country_life_expectancy
        WHERE avg_life_expectancy IS NOT NULL
    """
    engine = create_engine(DATABASE_URL)
    df = pd.read_sql(query, engine)
    if df.empty or len(df) < 10:
        raise ValueError(
            "No data (or too few rows) in mart_country_life_expectancy. "
            "Run the full pipeline first: ./run.sh ingest && ./run.sh transform && ./run.sh dbt-run && ./run.sh dbt-test"
        )
    return df


def prepare_features(df):
    le = LabelEncoder()
    df = df.copy()
    df["country_encoded"] = le.fit_transform(df["country_code"].astype(str))
    df["year_sq"] = df["year"] ** 2
    feature_cols = ["year", "year_sq", "country_encoded"]
    X = df[feature_cols]
    y = df["avg_life_expectancy"]
    return X, y, feature_cols, le


def train_and_log(model, model_name, X_train, X_test, y_train, y_test, feature_cols):
    """Train one model, log to MLflow, return test R²."""
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mse = mean_squared_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    mae = mean_absolute_error(y_test, preds)
    cv_r2 = cross_val_score(model, X_train, y_train, cv=5, scoring="r2").mean()

    mlflow.log_param("model_type", model_name)
    mlflow.log_param("features", ",".join(feature_cols))
    mlflow.log_metric("mse", mse)
    mlflow.log_metric("r2", r2)
    mlflow.log_metric("mae", mae)
    mlflow.log_metric("cv_r2_mean", cv_r2)

    # Default serialization (no skops) so all sklearn models log without untrusted-type errors
    mlflow.sklearn.log_model(model, name="model")

    logging.info(
        f"  {model_name} — MSE: {mse:.2f}, R2: {r2:.2f}, MAE: {mae:.2f} years"
    )
    return r2


def main():
    logging.info("Starting ML training job (multiple models)")

    wait_for_mlflow()
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    df = load_data()
    X, y, feature_cols, _ = prepare_features(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Regression baseline, tree, and ensemble with tuned params for better performance
    models = [
        (LinearRegression(), "LinearRegression"),
        (
            DecisionTreeRegressor(max_depth=15, min_samples_leaf=3, random_state=42),
            "DecisionTreeRegressor",
        ),
        (
            RandomForestRegressor(
                n_estimators=100, max_depth=12, min_samples_leaf=3, random_state=42
            ),
            "RandomForestRegressor",
        ),
        (
            HistGradientBoostingRegressor(
                max_iter=300, max_depth=8, min_samples_leaf=4, random_state=42
            ),
            "HistGradientBoostingRegressor",
        ),
    ]

    results = []
    for model, name in models:
        with mlflow.start_run(run_name=name):
            r2 = train_and_log(
                model, name, X_train, X_test, y_train, y_test, feature_cols
            )
            results.append((name, r2))

    best_name = max(results, key=lambda x: x[1])[0]
    logging.info("ML job finished successfully")
    logging.info("Best model by R²: %s (compare all runs in MLflow)", best_name)


if __name__ == "__main__":
    main()

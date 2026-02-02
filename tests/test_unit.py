"""Unit tests for data quality validation."""
import sys
from pathlib import Path

# Allow importing from transformations when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
from transformations.transform import validate_data


def test_validate_data_passes_on_clean_data():
    df = pd.DataFrame({
        "SpatialDimCode": ["RWA", "KEN"],
        "TimeDim": [2020, 2020],
        "Dim1": ["Both sexes", "Both sexes"],
        "NumericValue": [69.3, 66.7]
    })

    # Should not raise
    validate_data(df)


def test_validate_data_fails_on_nulls():
    df = pd.DataFrame({
        "SpatialDimCode": ["RWA"],
        "TimeDim": [2020],
        "Dim1": ["Both sexes"],
        "NumericValue": [None]
    })

    with pytest.raises(ValueError):
        validate_data(df)


def test_validate_data_fails_on_duplicates():
    df = pd.DataFrame({
        "SpatialDimCode": ["RWA", "RWA"],
        "TimeDim": [2020, 2020],
        "Dim1": ["Both sexes", "Both sexes"],
        "NumericValue": [69.3, 69.3]
    })

    with pytest.raises(ValueError):
        validate_data(df)

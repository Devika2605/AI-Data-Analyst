import os
import tempfile
import numpy as np
import pandas as pd
import pytest

import data_engine
import ml_engine


@pytest.fixture()
def anomaly_dataset():
    rng = np.random.default_rng(42)
    normal = rng.normal(100, 10, 200)
    values = np.concatenate([normal, [1000, -500]])  # 2 obvious anomalies
    df = pd.DataFrame({"sales": values, "profit": rng.normal(20, 5, len(values))})
    fd, path = tempfile.mkstemp(suffix=".csv")
    df.to_csv(path, index=False)
    meta = data_engine.validate_and_load_csv(path, "anomaly_test.csv")
    os.remove(path)
    return meta["dataset_id"]


@pytest.fixture()
def forecast_dataset():
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    values = np.linspace(100, 400, 60) + np.random.default_rng(1).normal(0, 5, 60)
    df = pd.DataFrame({"date": dates, "revenue": values})
    fd, path = tempfile.mkstemp(suffix=".csv")
    df.to_csv(path, index=False)
    meta = data_engine.validate_and_load_csv(path, "forecast_test.csv")
    os.remove(path)
    return meta["dataset_id"]


def test_anomaly_detection_finds_outliers(anomaly_dataset):
    result = ml_engine.detect_anomalies(anomaly_dataset, method="iqr")
    assert result["anomaly_count"] >= 1
    assert result["error"] is None


def test_anomaly_detection_insufficient_data():
    fd, path = tempfile.mkstemp(suffix=".csv")
    pd.DataFrame({"sales": [1, 2, 3]}).to_csv(path, index=False)
    meta = data_engine.validate_and_load_csv(path, "tiny.csv")
    os.remove(path)
    result = ml_engine.detect_anomalies(meta["dataset_id"])
    assert result["error"] == "insufficient_data"


def test_forecast_generates_future_points(forecast_dataset):
    result = ml_engine.forecast(forecast_dataset, None, None, horizon=14)
    assert result["sufficient_data"] is True
    forecast_points = [p for p in result["points"] if p["is_forecast"]]
    assert len(forecast_points) == 14


def test_forecast_fails_gracefully_with_no_date_column():
    fd, path = tempfile.mkstemp(suffix=".csv")
    pd.DataFrame({"a": [1, 2, 3, 4, 5]}).to_csv(path, index=False)
    meta = data_engine.validate_and_load_csv(path, "no_date.csv")
    os.remove(path)
    result = ml_engine.forecast(meta["dataset_id"], None, None, 30)
    assert result["sufficient_data"] is False

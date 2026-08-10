import os
import tempfile
import pandas as pd
import pytest

import agent
import data_engine


@pytest.fixture()
def sales_dataset():
    df = pd.DataFrame({
        "order_id": range(1, 21),
        "date": pd.date_range("2024-01-01", periods=20, freq="D"),
        "region": (["South", "North", "East", "West"] * 5),
        "product": (["Widget", "Gadget"] * 10),
        "sales": [100 + i * 5 for i in range(20)],
        "profit": [10 + i for i in range(20)],
    })
    fd, path = tempfile.mkstemp(suffix=".csv")
    df.to_csv(path, index=False)
    meta = data_engine.validate_and_load_csv(path, "agent_sales.csv")
    os.remove(path)
    return meta["dataset_id"]


def test_intent_classification_ranking(sales_dataset):
    meta = {sales_dataset: data_engine.get_metadata(sales_dataset)}
    intent, entities = agent.classify_intent("Which region generated the highest revenue?", meta, {})
    assert intent == "aggregation"


def test_intent_classification_trend(sales_dataset):
    meta = {sales_dataset: data_engine.get_metadata(sales_dataset)}
    intent, entities = agent.classify_intent("Show monthly sales trends", meta, {})
    assert intent == "trend"


def test_intent_classification_anomaly(sales_dataset):
    meta = {sales_dataset: data_engine.get_metadata(sales_dataset)}
    intent, entities = agent.classify_intent("Detect anomalies in the dataset", meta, {})
    assert intent == "anomaly"


def test_intent_classification_forecast(sales_dataset):
    meta = {sales_dataset: data_engine.get_metadata(sales_dataset)}
    intent, entities = agent.classify_intent("Forecast next month's revenue", meta, {})
    assert intent == "forecast"


def test_handle_chat_end_to_end_ranking(sales_dataset):
    response = agent.handle_chat("test-session", "Which region generated the highest sales?", [sales_dataset])
    assert response.get("error") is None
    assert response["result"] is not None
    assert response["sql"] is not None


def test_handle_chat_no_dataset_returns_error():
    response = agent.handle_chat("test-session-2", "Which region is best?", [])
    assert response["error"] is not None


def test_handle_chat_underperforming_asks_clarification(sales_dataset):
    response = agent.handle_chat("test-session-3", "Which products are underperforming?", [sales_dataset])
    assert response.get("clarification_needed")

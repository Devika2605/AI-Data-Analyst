import os
import tempfile
import pytest

import data_engine


@pytest.fixture()
def sample_dataset():
    content = (
        "order_id,date,region,category,sales,profit\n"
        "1,2024-01-01,South,Furniture,100,10\n"
        "2,2024-01-15,North,Tech,200,40\n"
        "3,2024-02-01,South,Tech,150,-5\n"
        "4,2024-02-10,East,Furniture,300,60\n"
        "4,2024-02-10,East,Furniture,300,60\n"  # duplicate row (identical to previous)
    )
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    meta = data_engine.validate_and_load_csv(path, "sample.csv")
    os.remove(path)
    return meta


def test_role_detection(sample_dataset):
    assert "sales" in sample_dataset["numeric_columns"]
    assert "profit" in sample_dataset["numeric_columns"]
    assert "region" in sample_dataset["categorical_columns"]
    assert "date" in sample_dataset["date_columns"]


def test_duplicate_row_detection(sample_dataset):
    assert sample_dataset["duplicate_rows"] == 1


def test_quality_score_in_range(sample_dataset):
    assert 0 <= sample_dataset["quality_score"] <= 100


def test_profile_returns_stats(sample_dataset):
    profiles = data_engine.profile_dataset(sample_dataset["dataset_id"])
    sales_profile = next(p for p in profiles if p["name"] == "sales")
    assert sales_profile["mean"] is not None
    assert sales_profile["min"] == 100


def test_sql_read_only_allows_select(sample_dataset):
    table = data_engine.get_table_names([sample_dataset["dataset_id"]])[sample_dataset["dataset_id"]]
    df = data_engine.run_sql([sample_dataset["dataset_id"]], f"SELECT region, SUM(sales) AS sales FROM {table} GROUP BY region")
    assert "region" in df.columns


def test_sql_blocks_destructive_statements(sample_dataset):
    with pytest.raises(ValueError):
        data_engine.run_sql([sample_dataset["dataset_id"]], "DROP TABLE sample")


def test_sql_blocks_non_select():
    with pytest.raises(ValueError):
        data_engine.validate_sql("DELETE FROM sample WHERE 1=1")

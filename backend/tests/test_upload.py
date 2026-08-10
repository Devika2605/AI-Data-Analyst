import os
import tempfile
import pytest

import data_engine


def _write_csv(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


def test_valid_csv_loads():
    path = _write_csv("region,revenue\nSouth,100\nNorth,200\n")
    meta = data_engine.validate_and_load_csv(path, "sales.csv")
    assert meta["rows"] == 2
    assert meta["columns"] == 2
    assert "region" in meta["column_names"]
    os.remove(path)


def test_empty_csv_rejected():
    path = _write_csv("")
    with pytest.raises(ValueError):
        data_engine.validate_and_load_csv(path, "empty.csv")
    os.remove(path)


def test_non_csv_extension_rejected():
    path = _write_csv("a,b\n1,2\n")
    with pytest.raises(ValueError):
        data_engine.validate_and_load_csv(path, "notes.txt")
    os.remove(path)


def test_header_only_csv_rejected():
    path = _write_csv("a,b,c\n")
    with pytest.raises(ValueError):
        data_engine.validate_and_load_csv(path, "headers_only.csv")
    os.remove(path)


def test_duplicate_columns_deduped():
    path = _write_csv("a,a,b\n1,2,3\n4,5,6\n")
    meta = data_engine.validate_and_load_csv(path, "dupe_cols.csv")
    assert len(meta["column_names"]) == len(set(meta["column_names"]))
    os.remove(path)

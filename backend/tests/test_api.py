import io
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_and_profile_flow():
    csv_content = b"region,revenue\nSouth,100\nNorth,200\nEast,150\n"
    resp = client.post(
        "/api/datasets/upload",
        files={"file": ("api_test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    dataset_id = body["dataset"]["dataset_id"]

    profile_resp = client.get(f"/api/datasets/{dataset_id}/profile")
    assert profile_resp.status_code == 200
    assert profile_resp.json()["rows"] == 3

    quality_resp = client.get(f"/api/datasets/{dataset_id}/quality")
    assert quality_resp.status_code == 200
    assert 0 <= quality_resp.json()["score"] <= 100


def test_upload_invalid_file_returns_friendly_error():
    resp = client.post(
        "/api/datasets/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]


def test_chat_after_upload():
    csv_content = b"region,revenue\nSouth,500\nNorth,300\n"
    upload = client.post(
        "/api/datasets/upload",
        files={"file": ("chat_test.csv", io.BytesIO(csv_content), "text/csv")},
    ).json()
    dataset_id = upload["dataset"]["dataset_id"]

    chat_resp = client.post("/api/chat", json={
        "session_id": "s1", "message": "Which region generated the highest revenue?",
        "dataset_ids": [dataset_id],
    })
    assert chat_resp.status_code == 200
    assert "South" in chat_resp.json()["answer"]


def test_dataset_not_found_returns_404():
    resp = client.get("/api/datasets/does-not-exist/profile")
    assert resp.status_code == 404

"""
run_eval.py — Runs the evaluation question set against the API (in-process,
via FastAPI TestClient) and prints a results table. Used to generate the
real numbers documented in docs/evaluation.md — nothing in that file is
fabricated; this script is how the numbers were produced.

Run from backend/: python run_eval.py
"""
import io
import json
import time

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def upload(path, name):
    with open(path, "rb") as f:
        content = f.read()
    resp = client.post("/api/datasets/upload", files={"file": (name, io.BytesIO(content), "text/csv")})
    return resp.json()["dataset"]["dataset_id"]


def ask(session_id, message, dataset_ids):
    t0 = time.time()
    resp = client.post("/api/chat", json={"session_id": session_id, "message": message, "dataset_ids": dataset_ids})
    dt = round((time.time() - t0) * 1000)
    return resp.json(), dt


def main():
    sales_id = upload("../datasets/sample_sales.csv", "sample_sales.csv")
    customers_id = upload("../datasets/sample_customers.csv", "sample_customers.csv")
    feedback_id = upload("../datasets/sample_feedback.csv", "sample_feedback.csv")

    questions = [
        ("Which region generated the highest revenue?", [sales_id]),
        ("Show monthly sales trends.", [sales_id]),
        ("What are the top five customers?", [sales_id]),
        ("Which products are underperforming?", [sales_id]),
        ("Detect anomalies.", [sales_id]),
        ("Generate SQL for this analysis.", [sales_id]),
        ("Forecast next month's revenue.", [sales_id]),
        ("Find customers complaining about delayed delivery.", [feedback_id]),
    ]

    print(f"{'#':<3} {'Question':<55} {'Type':<15} {'ms':<6} {'Has SQL':<8} {'Has Chart':<10} {'Error'}")
    print("-" * 115)
    session_id = "eval-session"
    for i, (q, ids) in enumerate(questions, 1):
        result, dt = ask(session_id, q, ids)
        print(f"{i:<3} {q[:53]:<55} {result.get('analysis_type', ''):<15} {dt:<6} "
              f"{'yes' if result.get('sql') else 'no':<8} "
              f"{'yes' if result.get('visualization') else 'no':<10} "
              f"{result.get('error') or ''}")

    # Underperforming should trigger clarification on first, unqualified ask
    print("\nClarification check (underperforming, no qualifier):")
    result, _ = ask("eval-session-2", "Which products are underperforming?", [sales_id])
    print(" clarification_needed:", bool(result.get("clarification_needed")))

    # Anomaly detail
    anomaly_resp = client.post("/api/anomalies", json={"dataset_id": sales_id, "method": "isolation_forest"}).json()
    print(f"\nAnomaly detection: {anomaly_resp['anomaly_count']} anomalies "
          f"({anomaly_resp['anomaly_percentage']}%) out of dataset")

    # Forecast detail
    forecast_resp = client.post("/api/forecast", json={"dataset_id": sales_id, "horizon": 30}).json()
    print(f"Forecast: sufficient_data={forecast_resp['sufficient_data']}, "
          f"target={forecast_resp['target_column']}, points={len(forecast_resp['points'])}")

    # Multi-file relationship detection
    rel_resp = client.get(f"/api/datasets/{sales_id}/relationships/{customers_id}").json()
    print(f"\nRelationship detection (sales <-> customers): {len(rel_resp['relationships'])} candidate(s) found")
    for r in rel_resp["relationships"]:
        print(" ", r)

    # Invalid CSV
    bad_resp = client.post("/api/datasets/upload", files={"file": ("bad.csv", io.BytesIO(b""), "text/csv")}).json()
    print(f"\nInvalid CSV handling: success={bad_resp['success']}, error='{bad_resp.get('error')}'")

    # Nonexistent column question
    result, _ = ask("eval-session-3", "What is the total zzz_nonexistent_column?", [sales_id])
    print(f"\nNonexistent-column question -> analysis_type={result.get('analysis_type')}, "
          f"error={result.get('error')}, warnings={result.get('warnings')}")


if __name__ == "__main__":
    main()

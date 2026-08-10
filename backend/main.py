"""
main.py — FastAPI entry point: app setup, middleware, CORS, and route handlers.
"""
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import agent
import data_engine
import database
import ml_engine
from config import settings
from schemas import (
    UploadResponse, DatasetMetadata, DataProfileResponse, DataQualityResponse,
    ChatRequest, ChatResponse, AnomalyRequest, AnomalyResponse,
    ForecastRequest, ForecastResponse, InsightsResponse,
    DashboardResponse, ReportExportRequest, ReportExportResponse,
)
from utils import setup_logging, log_event

setup_logging()
database.init_db()  # also called on startup; safe/idempotent, ensures tables exist even under TestClient

app = FastAPI(title="AI Data Analyst", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    database.init_db()
    log_event("startup", provider=settings.LLM_PROVIDER)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    log_event("request", request_id=request_id, path=request.url.path,
              method=request.method, status=response.status_code, duration_ms=duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_event("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"error": "An internal error occurred. Please try again."})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "time": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

@app.post("/api/datasets/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename or "upload.csv")
    tmp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        meta = data_engine.validate_and_load_csv(tmp_path, safe_name)
        database.save_dataset_meta(meta["dataset_id"], meta["filename"], meta["uploaded_at"], meta)

        # Auto-index text columns for semantic search (best-effort, non-blocking failure)
        try:
            if meta["text_columns"] and settings.SEMANTIC_SEARCH_ENABLED:
                agent.maybe_index_text_columns(meta["dataset_id"], meta)
        except Exception as e:  # noqa: BLE001
            log_event("chroma_index_failed", error=str(e))

        log_event("dataset_uploaded", dataset_id=meta["dataset_id"], filename=safe_name, rows=meta["rows"])
        return UploadResponse(success=True, dataset=_to_dataset_metadata(meta))
    except ValueError as e:
        return UploadResponse(success=False, error=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/api/datasets")
def list_datasets():
    return {"datasets": [_to_dataset_metadata(m).model_dump() for m in data_engine.list_datasets()]}


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    try:
        meta = data_engine.get_metadata(dataset_id)
        preview = data_engine.get_preview(dataset_id)
        return {"dataset": _to_dataset_metadata(meta).model_dump(), "preview": preview}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/datasets/{dataset_id}/profile", response_model=DataProfileResponse)
def get_profile(dataset_id: str):
    try:
        profiles = data_engine.profile_dataset(dataset_id)
        meta = data_engine.get_metadata(dataset_id)
        return DataProfileResponse(dataset_id=dataset_id, rows=meta["rows"], columns=meta["columns"],
                                    column_profiles=profiles)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/datasets/{dataset_id}/quality", response_model=DataQualityResponse)
def get_quality(dataset_id: str):
    try:
        meta = data_engine.get_metadata(dataset_id)
        return DataQualityResponse(
            dataset_id=dataset_id, score=meta["quality_score"],
            checks_passed=meta["quality_checks"], issues=meta["quality_issues"],
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/datasets/{a}/relationships/{b}")
def get_relationships(a: str, b: str):
    try:
        return {"relationships": data_engine.detect_relationships([a, b])}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    result = agent.handle_chat(req.session_id, req.message, req.dataset_ids)
    return ChatResponse(**result)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

@app.post("/api/anomalies", response_model=AnomalyResponse)
def anomalies(req: AnomalyRequest):
    try:
        result = ml_engine.detect_anomalies(req.dataset_id, req.column, req.method)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    chart = None
    if result["anomalies"]:
        rows = [{"row_index": a["row_index"], "anomaly_score": a["anomaly_score"]} for a in result["anomalies"][:30]]
        chart = {"type": "scatter", "title": "Anomaly scores", "data": rows,
                 "x_key": "row_index", "y_key": "anomaly_score"}
    return AnomalyResponse(
        dataset_id=req.dataset_id, method=req.method,
        columns_analyzed=result["columns_analyzed"], anomaly_count=result["anomaly_count"],
        anomaly_percentage=result["anomaly_percentage"], anomalies=result["anomalies"],
        visualization=chart, explanation=result["explanation"], error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    try:
        result = ml_engine.forecast(req.dataset_id, req.date_column, req.target_column, req.horizon)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    chart = None
    if result["sufficient_data"]:
        chart = {"type": "line", "title": f"{result['target_column']} forecast",
                 "data": result["points"], "x_key": "date", "y_key": "value"}
    return ForecastResponse(
        dataset_id=req.dataset_id, date_column=result["date_column"], target_column=result["target_column"],
        sufficient_data=result["sufficient_data"], points=result["points"],
        visualization=chart, explanation=result["explanation"], error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

@app.post("/api/insights", response_model=InsightsResponse)
def insights(req: AnomalyRequest):  # reuses {dataset_id} shape
    try:
        meta = data_engine.get_metadata(req.dataset_id)
        result = agent.generate_insights(req.dataset_id, meta)
        return InsightsResponse(dataset_id=req.dataset_id, insights=result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.post("/api/dashboard/generate", response_model=DashboardResponse)
def dashboard(req: AnomalyRequest):
    try:
        result = agent.generate_dashboard(req.dataset_id)
        return DashboardResponse(dataset_id=req.dataset_id, kpis=result["kpis"], charts=result["charts"])
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.post("/api/reports/export", response_model=ReportExportResponse)
def export_report(req: ReportExportRequest):
    try:
        meta = data_engine.get_metadata(req.dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    lines = [f"# AI Data Analyst Report — {meta['filename']}", "",
              f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
              "## Dataset Summary", "",
              f"- Rows: {meta['rows']}", f"- Columns: {meta['columns']}",
              f"- Duplicate rows: {meta['duplicate_rows']}", f"- Quality score: {meta['quality_score']}/100", ""]

    if req.include_insights:
        lines.append("## Key Insights\n")
        for ins in agent.generate_insights(req.dataset_id, meta):
            lines.append(f"**{ins['title']}**: {ins['explanation']}\n")

    if req.include_anomalies:
        result = ml_engine.detect_anomalies(req.dataset_id)
        lines.append("## Anomaly Findings\n")
        lines.append(result["explanation"] + "\n")

    if req.include_forecast and meta["date_columns"] and meta["numeric_columns"]:
        fc = ml_engine.forecast(req.dataset_id, None, None, 30)
        lines.append("## Forecast\n")
        lines.append(fc["explanation"] + "\n")

    if req.session_id:
        history = database.get_recent_context(req.session_id, limit=20)
        if history:
            lines.append("## Selected Q&A\n")
            for turn in history:
                if turn["role"] == "user":
                    lines.append(f"**Q:** {turn['content']}")
                else:
                    lines.append(f"**A:** {turn['content']}\n")

    return ReportExportResponse(report_markdown="\n".join(lines), generated_at=datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
def _to_dataset_metadata(meta: dict) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id=meta["dataset_id"], filename=meta["filename"], rows=meta["rows"],
        columns=meta["columns"], size_bytes=meta["size_bytes"], uploaded_at=meta["uploaded_at"],
        column_names=meta["column_names"], numeric_columns=meta["numeric_columns"],
        categorical_columns=meta["categorical_columns"], date_columns=meta["date_columns"],
        text_columns=meta["text_columns"], duplicate_rows=meta["duplicate_rows"],
        quality_score=meta["quality_score"], warnings=meta["warnings"],
    )

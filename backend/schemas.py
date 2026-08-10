"""
schemas.py — Pydantic models for request/response validation across the API.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

class ColumnInfo(BaseModel):
    name: str
    dtype: str
    role: str  # "numeric" | "categorical" | "date" | "text" | "id"
    missing_count: int
    missing_pct: float
    unique_count: int
    sample_values: list = Field(default_factory=list)
    min: Optional[Any] = None
    max: Optional[Any] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    top_categories: Optional[list] = None
    earliest: Optional[str] = None
    latest: Optional[str] = None
    detected_frequency: Optional[str] = None


class DatasetMetadata(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    size_bytes: int
    uploaded_at: str
    column_names: list[str]
    numeric_columns: list[str]
    categorical_columns: list[str]
    date_columns: list[str]
    text_columns: list[str]
    duplicate_rows: int
    quality_score: float
    warnings: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    success: bool
    dataset: Optional[DatasetMetadata] = None
    error: Optional[str] = None


class DataProfileResponse(BaseModel):
    dataset_id: str
    rows: int
    columns: int
    column_profiles: list[ColumnInfo]


class DataQualityIssue(BaseModel):
    severity: str  # "info" | "warning" | "error"
    message: str


class DataQualityResponse(BaseModel):
    dataset_id: str
    score: float
    checks_passed: list[str]
    issues: list[DataQualityIssue]


# ---------------------------------------------------------------------------
# Chat / Agent
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_ids: list[str] = Field(default_factory=list)


class ChartSpec(BaseModel):
    type: str
    title: str
    data: list[dict]
    x_key: Optional[str] = None
    y_key: Optional[str] = None
    y_keys: Optional[list[str]] = None
    category_key: Optional[str] = None
    value_key: Optional[str] = None


class ResultTable(BaseModel):
    columns: list[str]
    rows: list[list]


class ChatResponse(BaseModel):
    answer: str
    analysis_type: str
    methodology: list[str] = Field(default_factory=list)
    result: Optional[ResultTable] = None
    visualization: Optional[ChartSpec] = None
    generated_code: Optional[str] = None
    sql: Optional[str] = None
    sources: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    clarification_needed: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

class AnomalyRequest(BaseModel):
    dataset_id: str
    column: Optional[str] = None
    method: str = "isolation_forest"  # or "iqr"


class AnomalyRecord(BaseModel):
    row_index: int
    values: dict
    anomaly_score: float
    severity: str
    reason: str


class AnomalyResponse(BaseModel):
    dataset_id: str
    method: str
    columns_analyzed: list[str]
    anomaly_count: int
    anomaly_percentage: float
    anomalies: list[AnomalyRecord]
    visualization: Optional[ChartSpec] = None
    explanation: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ForecastRequest(BaseModel):
    dataset_id: str
    date_column: Optional[str] = None
    target_column: Optional[str] = None
    horizon: int = 30


class ForecastPoint(BaseModel):
    date: str
    value: float
    lower: Optional[float] = None
    upper: Optional[float] = None
    is_forecast: bool = False


class ForecastResponse(BaseModel):
    dataset_id: str
    date_column: Optional[str] = None
    target_column: Optional[str] = None
    sufficient_data: bool
    points: list[ForecastPoint] = Field(default_factory=list)
    visualization: Optional[ChartSpec] = None
    explanation: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

class Insight(BaseModel):
    title: str
    metric: str
    value: str
    explanation: str
    chart: Optional[ChartSpec] = None


class InsightsResponse(BaseModel):
    dataset_id: str
    insights: list[Insight]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class KPI(BaseModel):
    label: str
    value: str
    raw_value: Optional[float] = None


class DashboardResponse(BaseModel):
    dataset_id: str
    kpis: list[KPI]
    charts: list[ChartSpec]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportExportRequest(BaseModel):
    dataset_id: str
    session_id: Optional[str] = None
    include_anomalies: bool = True
    include_forecast: bool = True
    include_insights: bool = True


class ReportExportResponse(BaseModel):
    report_markdown: str
    generated_at: str

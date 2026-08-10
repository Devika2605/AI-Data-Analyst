"""
data_engine.py — CSV loading, validation, schema detection, profiling,
data-quality scoring, and safe DuckDB SQL execution.

This module is the deterministic "ground truth" layer of the application.
The LLM never computes numbers itself — everything numeric flows through here.
"""
import os
import re
import uuid
import duckdb
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from config import settings

# In-memory registry of loaded datasets: dataset_id -> dict(meta + dataframe)
_REGISTRY: dict[str, dict] = {}

DANGEROUS_SQL_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "attach", "copy",
    "pragma", "call", "install", "load", "export", "import",
    "create table", "create view", "replace", "vacuum",
]


# ---------------------------------------------------------------------------
# Loading & validation
# ---------------------------------------------------------------------------

def validate_and_load_csv(file_path: str, filename: str) -> dict:
    """Validate a CSV file and load it into the registry. Returns metadata dict."""
    warnings: list[str] = []

    if not filename.lower().endswith(".csv"):
        raise ValueError("Only .csv files are supported.")

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        raise ValueError("The uploaded file is empty.")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValueError(f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.")

    # Try a few encodings — real-world CSVs are messy
    df = None
    last_err = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(file_path, encoding=enc, on_bad_lines="warn", engine="python")
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    if df is None:
        raise ValueError(f"Could not parse CSV file: {last_err}")

    if df.shape[0] == 0:
        raise ValueError("CSV has headers but no data rows.")
    if df.shape[1] == 0:
        raise ValueError("CSV has no columns.")

    # Normalize column names (strip whitespace, keep readable)
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        warnings.append("Duplicate column names detected; duplicates were suffixed.")
        df.columns = _dedupe_columns(df.columns)

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        warnings.append(f"{duplicate_rows} duplicate rows detected.")

    dataset_id = str(uuid.uuid4())[:8]
    roles = _detect_roles(df)

    quality_score, quality_checks, quality_issues = _compute_quality(df, roles, duplicate_rows)

    meta = {
        "dataset_id": dataset_id,
        "filename": filename,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "size_bytes": size_bytes,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "column_names": list(df.columns),
        "roles": roles,
        "numeric_columns": [c for c, r in roles.items() if r == "numeric"],
        "categorical_columns": [c for c, r in roles.items() if r == "categorical"],
        "date_columns": [c for c, r in roles.items() if r == "date"],
        "text_columns": [c for c, r in roles.items() if r == "text"],
        "duplicate_rows": duplicate_rows,
        "quality_score": quality_score,
        "quality_checks": quality_checks,
        "quality_issues": quality_issues,
        "warnings": warnings,
    }

    _REGISTRY[dataset_id] = {"df": df, "meta": meta}
    return meta


def _dedupe_columns(cols):
    seen = {}
    out = []
    for c in cols:
        if c not in seen:
            seen[c] = 0
            out.append(c)
        else:
            seen[c] += 1
            out.append(f"{c}_{seen[c]}")
    return out


def _detect_roles(df: pd.DataFrame) -> dict:
    """Classify every column as numeric / date / categorical / text / id."""
    roles = {}
    n = len(df)
    for col in df.columns:
        series = df[col]
        lower = col.lower()
        tokens = re.split(r"[_\s\-]+", lower)

        # ID-like columns: identified by name pattern (order_id, customer_id, sku_code, uuid...)
        # regardless of cardinality — these are identifiers, not analytical dimensions or metrics.
        if tokens and tokens[-1] in ("id", "code", "uuid", "key") and lower not in ("valid", "paid"):
            roles[col] = "id"
            continue

        if pd.api.types.is_numeric_dtype(series):
            roles[col] = "numeric"
            continue

        # Try date parsing
        if _looks_like_date(series, lower):
            roles[col] = "date"
            continue

        # Text vs categorical: long average string length / low repetition => text
        if series.dtype == object:
            sample = series.dropna().astype(str)
            if len(sample) == 0:
                roles[col] = "categorical"
                continue
            avg_len = sample.str.len().mean()
            uniqueness = series.nunique() / max(n, 1)
            if avg_len > 40 or (avg_len > 20 and uniqueness > 0.5):
                roles[col] = "text"
            else:
                roles[col] = "categorical"
        else:
            roles[col] = "categorical"
    return roles


def _looks_like_date(series: pd.Series, lower_name: str) -> bool:
    hints = ["date", "time", "created", "updated", "timestamp", "day", "month", "year"]
    name_hint = any(h in lower_name for h in hints)
    sample = series.dropna().astype(str).head(30)
    if len(sample) == 0:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        success_rate = parsed.notna().mean()
    except Exception:  # noqa: BLE001
        success_rate = 0
    return success_rate > 0.85 and (name_hint or success_rate > 0.95)


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def _compute_quality(df: pd.DataFrame, roles: dict, duplicate_rows: int):
    checks_passed = []
    issues = []
    score = 100.0
    n_rows, n_cols = df.shape

    # Missing values
    missing_pct_total = float(df.isna().mean().mean() * 100) if n_cols else 0
    if missing_pct_total < 1:
        checks_passed.append("Missing values within acceptable range")
    else:
        penalty = min(25, missing_pct_total * 1.5)
        score -= penalty
        issues.append({"severity": "warning", "message": f"{missing_pct_total:.1f}% missing values across dataset"})

    # Duplicates
    dup_pct = (duplicate_rows / n_rows * 100) if n_rows else 0
    if dup_pct == 0:
        checks_passed.append("No duplicate rows")
    else:
        penalty = min(15, dup_pct)
        score -= penalty
        issues.append({"severity": "warning", "message": f"{duplicate_rows} duplicate rows ({dup_pct:.1f}%)"})

    # Constant columns
    constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    if constant_cols:
        score -= min(10, 3 * len(constant_cols))
        issues.append({"severity": "warning", "message": f"Constant columns detected: {', '.join(constant_cols)}"})
    else:
        checks_passed.append("No constant columns")

    # Empty columns
    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        score -= min(10, 5 * len(empty_cols))
        issues.append({"severity": "error", "message": f"Entirely empty columns: {', '.join(empty_cols)}"})

    # High cardinality categorical (possible ID misclassification)
    high_card = [
        c for c, r in roles.items()
        if r == "categorical" and df[c].nunique(dropna=True) / max(n_rows, 1) > 0.8
    ]
    if high_card:
        issues.append({"severity": "info", "message": f"High-cardinality columns: {', '.join(high_card)}"})

    # Extreme values / outliers on numeric columns via IQR (informational)
    numeric_cols = [c for c, r in roles.items() if r == "numeric"]
    extreme_flagged = []
    for c in numeric_cols:
        col = df[c].dropna()
        if len(col) < 10:
            continue
        q1, q3 = col.quantile(0.25), col.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
        extreme = ((col < lower) | (col > upper)).sum()
        if extreme > 0:
            extreme_flagged.append(f"{c} ({extreme})")
    if extreme_flagged:
        issues.append({"severity": "info", "message": f"Potential extreme values: {', '.join(extreme_flagged)}"})
    else:
        checks_passed.append("No severe extreme values detected")

    # Schema validity
    if n_cols > 0 and n_rows > 0:
        checks_passed.append("Schema valid (headers + data rows present)")

    if roles and any(r == "date" for r in roles.values()):
        checks_passed.append("Date column detected")
    if roles and any(r == "numeric" for r in roles.values()):
        checks_passed.append("Numeric columns valid")

    score = max(0.0, min(100.0, round(score, 1)))
    return score, checks_passed, issues


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------

def profile_dataset(dataset_id: str) -> list[dict]:
    df, meta = _get(dataset_id)
    roles = meta["roles"]
    profiles = []
    n = len(df)

    for col in df.columns:
        series = df[col]
        role = roles.get(col, "categorical")
        missing_count = int(series.isna().sum())
        info = {
            "name": col,
            "dtype": str(series.dtype),
            "role": role,
            "missing_count": missing_count,
            "missing_pct": round(missing_count / n * 100, 2) if n else 0,
            "unique_count": int(series.nunique(dropna=True)),
            "sample_values": [_jsonable(v) for v in series.dropna().unique()[:5]],
        }

        if role == "numeric":
            desc = series.describe()
            info.update({
                "min": _jsonable(desc.get("min")),
                "max": _jsonable(desc.get("max")),
                "mean": round(float(desc.get("mean")), 2) if pd.notna(desc.get("mean")) else None,
                "median": round(float(series.median()), 2) if series.notna().any() else None,
                "std": round(float(desc.get("std")), 2) if pd.notna(desc.get("std")) else None,
                "q1": round(float(series.quantile(0.25)), 2) if series.notna().any() else None,
                "q3": round(float(series.quantile(0.75)), 2) if series.notna().any() else None,
            })
        elif role == "date":
            parsed = pd.to_datetime(series, errors="coerce", format="mixed")
            if parsed.notna().any():
                info["earliest"] = str(parsed.min())
                info["latest"] = str(parsed.max())
                info["detected_frequency"] = _infer_frequency(parsed.dropna())
        elif role in ("categorical", "text", "id"):
            top = series.value_counts(dropna=True).head(5)
            info["top_categories"] = [{"value": _jsonable(k), "count": int(v)} for k, v in top.items()]

        profiles.append(info)
    return profiles


def _infer_frequency(parsed: pd.Series) -> str:
    try:
        diffs = parsed.sort_values().diff().dropna().dt.days
        if len(diffs) == 0:
            return "unknown"
        median_gap = diffs.median()
        if median_gap <= 1:
            return "daily"
        if median_gap <= 8:
            return "weekly"
        if median_gap <= 32:
            return "monthly"
        if median_gap <= 95:
            return "quarterly"
        return "yearly"
    except Exception:  # noqa: BLE001
        return "unknown"


def _jsonable(v):
    if pd.isna(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    return v


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def _get(dataset_id: str):
    if dataset_id not in _REGISTRY:
        raise KeyError(f"Dataset {dataset_id} not found. Upload it first.")
    entry = _REGISTRY[dataset_id]
    return entry["df"], entry["meta"]


def get_metadata(dataset_id: str) -> dict:
    _, meta = _get(dataset_id)
    return meta


PRIMARY_METRIC_SYNONYMS = ["revenue", "sales", "amount", "turnover", "income", "profit", "total"]
PRIMARY_DIMENSION_SYNONYMS = ["region", "category", "product", "segment", "department", "channel"]


def pick_primary_dimension(categorical_columns: list[str]) -> str | None:
    """Prefer natural business dimensions (region/category/product/...) over
    identity-like categoricals (customer_name, etc.) for default groupings."""
    if not categorical_columns:
        return None
    for syn in PRIMARY_DIMENSION_SYNONYMS:
        for col in categorical_columns:
            if syn in col.lower():
                return col
    return categorical_columns[0]


def pick_primary_metric(numeric_columns: list[str]) -> str | None:
    """Prefer business-value columns (revenue/sales/profit/...) over counts/quantities
    when no explicit metric is requested."""
    if not numeric_columns:
        return None
    for syn in PRIMARY_METRIC_SYNONYMS:
        for col in numeric_columns:
            if syn in col.lower():
                return col
    return numeric_columns[0]


def get_dataframe(dataset_id: str) -> pd.DataFrame:
    df, _ = _get(dataset_id)
    return df


def list_datasets() -> list[dict]:
    return [entry["meta"] for entry in _REGISTRY.values()]


def get_preview(dataset_id: str, n: int = 20) -> dict:
    df, _ = _get(dataset_id)
    head = df.head(n)
    return {"columns": list(head.columns), "rows": head.where(pd.notna(head), None).values.tolist()}


# ---------------------------------------------------------------------------
# Safe SQL execution via DuckDB
# ---------------------------------------------------------------------------

def validate_sql(sql: str) -> None:
    """Raise ValueError if SQL contains anything other than a read-only SELECT."""
    normalized = re.sub(r"\s+", " ", sql.strip().lower())
    if not normalized.startswith("select") and not normalized.startswith("with"):
        raise ValueError("Only SELECT queries are permitted.")
    for kw in DANGEROUS_SQL_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", normalized):
            raise ValueError(f"Query contains disallowed keyword: '{kw}'.")
    if ";" in sql.strip().rstrip(";"):
        raise ValueError("Multiple statements are not permitted.")


def run_sql(dataset_ids: list[str], sql: str) -> pd.DataFrame:
    """Execute read-only SQL across one or more registered datasets using DuckDB.
    Each dataset is registered as a table named after its (sanitized) filename stem,
    and also accessible via its dataset_id.
    """
    validate_sql(sql)
    con = duckdb.connect(database=":memory:")
    try:
        for did in dataset_ids:
            df, meta = _get(did)
            table_name = _table_name(meta)
            con.register(table_name, df)
            con.register(did, df)  # also allow raw dataset_id reference
        result = con.execute(sql).fetch_df()
        if len(result) > settings.MAX_RESULT_ROWS:
            result = result.head(settings.MAX_RESULT_ROWS)
        return result
    finally:
        con.close()


def _table_name(meta: dict) -> str:
    stem = os.path.splitext(meta["filename"])[0]
    stem = re.sub(r"[^a-zA-Z0-9_]", "_", stem)
    if not stem or stem[0].isdigit():
        stem = f"t_{stem}"
    return stem


def get_table_names(dataset_ids: list[str]) -> dict:
    """Return {dataset_id: table_name} for the given datasets."""
    out = {}
    for did in dataset_ids:
        _, meta = _get(did)
        out[did] = _table_name(meta)
    return out


# ---------------------------------------------------------------------------
# Multi-file relationship detection
# ---------------------------------------------------------------------------

def detect_relationships(dataset_ids: list[str]) -> list[dict]:
    """Detect likely join keys between datasets based on column name overlap
    and value overlap."""
    relationships = []
    metas = {did: get_metadata(did) for did in dataset_ids}
    dfs = {did: get_dataframe(did) for did in dataset_ids}

    for i, a in enumerate(dataset_ids):
        for b in dataset_ids[i + 1:]:
            cols_a = set(metas[a]["column_names"])
            cols_b = set(metas[b]["column_names"])
            shared = cols_a & cols_b
            for col in shared:
                try:
                    va = set(dfs[a][col].dropna().astype(str).unique()[:1000])
                    vb = set(dfs[b][col].dropna().astype(str).unique()[:1000])
                    if not va or not vb:
                        continue
                    overlap = len(va & vb) / max(1, min(len(va), len(vb)))
                    if overlap > 0.3:
                        relationships.append({
                            "left_dataset": a,
                            "right_dataset": b,
                            "column": col,
                            "overlap_ratio": round(overlap, 2),
                        })
                except Exception:  # noqa: BLE001
                    continue
    return relationships

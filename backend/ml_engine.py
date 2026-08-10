"""
ml_engine.py — Deterministic ML/statistics layer.
Anomaly detection (Isolation Forest + IQR) and lightweight forecasting.
The LLM never invents these results; it only explains verified output.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import data_engine


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(dataset_id: str, column: str | None = None, method: str = "isolation_forest") -> dict:
    df = data_engine.get_dataframe(dataset_id)
    meta = data_engine.get_metadata(dataset_id)
    numeric_cols = meta["numeric_columns"]

    if not numeric_cols:
        return {
            "columns_analyzed": [],
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomalies": [],
            "explanation": "No numeric columns were found, so anomaly detection could not be performed.",
            "error": "no_numeric_columns",
        }

    columns_analyzed = [column] if column and column in numeric_cols else numeric_cols
    work = df[columns_analyzed].copy()
    work = work.apply(pd.to_numeric, errors="coerce")
    valid_mask = work.notna().all(axis=1)
    clean = work[valid_mask]

    if len(clean) < 10:
        return {
            "columns_analyzed": columns_analyzed,
            "anomaly_count": 0,
            "anomaly_percentage": 0.0,
            "anomalies": [],
            "explanation": "Not enough complete numeric rows (minimum 10 required) to reliably detect anomalies.",
            "error": "insufficient_data",
        }

    if method == "iqr" or len(columns_analyzed) == 1:
        anomalies = _iqr_anomalies(clean, columns_analyzed, df)
    else:
        anomalies = _isolation_forest_anomalies(clean, columns_analyzed, df)

    pct = round(len(anomalies) / len(df) * 100, 2) if len(df) else 0.0
    explanation = (
        f"Analyzed {len(clean)} complete rows across {len(columns_analyzed)} numeric column(s) "
        f"using {'Isolation Forest' if method != 'iqr' and len(columns_analyzed) > 1 else 'IQR (Interquartile Range)'}. "
        f"Found {len(anomalies)} anomalous row(s) ({pct}% of the dataset)."
    )

    return {
        "columns_analyzed": columns_analyzed,
        "anomaly_count": len(anomalies),
        "anomaly_percentage": pct,
        "anomalies": anomalies[:100],
        "explanation": explanation,
        "error": None,
    }


def _iqr_anomalies(clean: pd.DataFrame, columns: list[str], full_df: pd.DataFrame) -> list[dict]:
    results = []
    bounds = {}
    for c in columns:
        q1, q3 = clean[c].quantile(0.25), clean[c].quantile(0.75)
        iqr = q3 - q1
        bounds[c] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)

    for idx, row in clean.iterrows():
        reasons = []
        max_dev = 0.0
        for c in columns:
            lower, upper = bounds[c]
            if row[c] < lower or row[c] > upper:
                direction = "above" if row[c] > upper else "below"
                bound = upper if direction == "above" else lower
                dev = abs(row[c] - bound) / (abs(bound) + 1e-9)
                max_dev = max(max_dev, dev)
                reasons.append(f"{c}={row[c]:.2f} is {direction} the normal IQR range "
                                f"[{lower:.2f}, {upper:.2f}]")
        if reasons:
            score = min(1.0, round(max_dev, 3))
            results.append({
                "row_index": int(idx),
                "values": {c: _safe_float(full_df.loc[idx, c]) for c in full_df.columns
                           if c in columns or full_df.columns.get_loc(c) < 6},
                "anomaly_score": score,
                "severity": _severity(score),
                "reason": "; ".join(reasons),
            })
    results.sort(key=lambda r: r["anomaly_score"], reverse=True)
    return results


def _isolation_forest_anomalies(clean: pd.DataFrame, columns: list[str], full_df: pd.DataFrame) -> list[dict]:
    contamination = 0.05
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    model.fit(clean.values)
    raw_scores = model.decision_function(clean.values)  # higher = more normal
    preds = model.predict(clean.values)  # -1 = anomaly, 1 = normal

    # Normalize scores to 0..1 where 1 = most anomalous
    normalized = (raw_scores.max() - raw_scores) / (raw_scores.max() - raw_scores.min() + 1e-9)

    results = []
    for pos, idx in enumerate(clean.index):
        if preds[pos] == -1:
            score = round(float(normalized[pos]), 3)
            row = clean.loc[idx]
            # Determine which column(s) deviate most from the column mean (z-score) for explanation
            zscores = {c: abs((row[c] - clean[c].mean()) / (clean[c].std() + 1e-9)) for c in columns}
            worst_col = max(zscores, key=zscores.get)
            results.append({
                "row_index": int(idx),
                "values": {c: _safe_float(full_df.loc[idx, c]) for c in full_df.columns
                           if c in columns or full_df.columns.get_loc(c) < 6},
                "anomaly_score": score,
                "severity": _severity(score),
                "reason": (f"Flagged by Isolation Forest as a multivariate outlier across "
                           f"{', '.join(columns)}. Most deviant feature: {worst_col} "
                           f"(z-score={zscores[worst_col]:.2f})."),
            })
    results.sort(key=lambda r: r["anomaly_score"], reverse=True)
    return results


def _severity(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _safe_float(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 4)
    return v if not isinstance(v, (pd.Timestamp,)) else str(v)


# ---------------------------------------------------------------------------
# Forecasting — lightweight linear-trend + seasonal-naive blend
# ---------------------------------------------------------------------------

def forecast(dataset_id: str, date_column: str | None, target_column: str | None, horizon: int = 30) -> dict:
    df = data_engine.get_dataframe(dataset_id)
    meta = data_engine.get_metadata(dataset_id)

    date_col = date_column or (meta["date_columns"][0] if meta["date_columns"] else None)
    target_col = target_column or data_engine.pick_primary_metric(meta["numeric_columns"])

    if not date_col or not target_col:
        return {
            "date_column": date_col,
            "target_column": target_col,
            "sufficient_data": False,
            "points": [],
            "explanation": "I found insufficient historical data to generate a reliable forecast "
                            "(no usable date or numeric column was identified).",
            "error": "missing_columns",
        }

    work = df[[date_col, target_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce", format="mixed")
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce")
    work = work.dropna()

    if len(work) < 14:
        return {
            "date_column": date_col,
            "target_column": target_col,
            "sufficient_data": False,
            "points": [],
            "explanation": "I found insufficient historical data to generate a reliable forecast "
                            f"(only {len(work)} valid date/value rows; at least 14 are required).",
            "error": "insufficient_data",
        }

    # Aggregate to daily totals, then resample to fill gaps
    daily = work.groupby(work[date_col].dt.date)[target_col].sum()
    daily.index = pd.to_datetime(daily.index)
    daily = daily.asfreq("D", fill_value=0).sort_index()

    if len(daily) < 14:
        return {
            "date_column": date_col,
            "target_column": target_col,
            "sufficient_data": False,
            "points": [],
            "explanation": "I found insufficient historical data to generate a reliable forecast "
                            "after aggregating by day.",
            "error": "insufficient_data",
        }

    y = daily.values.astype(float)
    x = np.arange(len(y))

    # Linear regression trend
    coeffs = np.polyfit(x, y, 1)
    trend = np.polyval(coeffs, x)
    residuals = y - trend
    resid_std = float(np.std(residuals)) if len(residuals) > 1 else 0.0

    # Weekly seasonality (day-of-week average residual)
    dow = daily.index.dayofweek
    seasonal_avg = {d: float(np.mean(residuals[dow == d])) if np.any(dow == d) else 0.0 for d in range(7)}

    future_x = np.arange(len(y), len(y) + horizon)
    future_dates = pd.date_range(daily.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    future_trend = np.polyval(coeffs, future_x)
    future_seasonal = np.array([seasonal_avg[d] for d in future_dates.dayofweek])
    future_values = np.clip(future_trend + future_seasonal, a_min=0, a_max=None)

    points = []
    for i, (d, v) in enumerate(zip(daily.index, y)):
        points.append({"date": str(d.date()), "value": round(float(v), 2), "is_forecast": False})
    for i, (d, v) in enumerate(zip(future_dates, future_values)):
        margin = 1.28 * resid_std * np.sqrt(1 + (i + 1) / max(len(y), 1))  # ~80% interval, widening
        points.append({
            "date": str(d.date()),
            "value": round(float(v), 2),
            "lower": round(max(0.0, float(v - margin)), 2),
            "upper": round(float(v + margin), 2),
            "is_forecast": True,
        })

    slope_direction = "increasing" if coeffs[0] > 0 else ("decreasing" if coeffs[0] < 0 else "flat")
    explanation = (
        f"Aggregated {target_col} by day across {len(daily)} days of history. "
        f"Fitted a linear trend plus weekly seasonality. The underlying trend is {slope_direction} "
        f"(~{coeffs[0]:.2f} units/day). Forecast horizon: {horizon} days, with an approximate 80% "
        f"confidence interval based on historical residual variance."
    )

    return {
        "date_column": date_col,
        "target_column": target_col,
        "sufficient_data": True,
        "points": points,
        "explanation": explanation,
        "error": None,
    }

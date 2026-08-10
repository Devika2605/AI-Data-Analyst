"""
visualization.py — Builds validated, structured chart specifications from
already-computed result data. The backend never sends raw code to the
frontend for chart rendering — only structured data + chart type.
"""
import pandas as pd


def build_chart_spec(result_df: pd.DataFrame, chart_type: str | None = None, title: str = "") -> dict | None:
    """Infer (or accept) a chart type and produce a Recharts-friendly spec."""
    if result_df is None or result_df.empty:
        return None

    cols = list(result_df.columns)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(result_df[c])]
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    if chart_type is None:
        chart_type = _infer_chart_type(result_df, numeric_cols, non_numeric_cols)

    if chart_type is None:
        return None

    data = result_df.where(pd.notna(result_df), None).to_dict(orient="records")

    spec = {"type": chart_type, "title": title, "data": data}

    if chart_type in ("bar", "hbar", "line", "area"):
        x_key = non_numeric_cols[0] if non_numeric_cols else cols[0]
        y_keys = numeric_cols if numeric_cols else [cols[-1]]
        spec["x_key"] = x_key
        spec["y_key"] = y_keys[0]
        spec["y_keys"] = y_keys
    elif chart_type in ("pie", "donut"):
        spec["category_key"] = non_numeric_cols[0] if non_numeric_cols else cols[0]
        spec["value_key"] = numeric_cols[0] if numeric_cols else cols[-1]
    elif chart_type == "scatter":
        if len(numeric_cols) >= 2:
            spec["x_key"] = numeric_cols[0]
            spec["y_key"] = numeric_cols[1]
    elif chart_type in ("histogram", "box"):
        spec["value_key"] = numeric_cols[0] if numeric_cols else cols[0]

    return spec


def _infer_chart_type(df: pd.DataFrame, numeric_cols: list[str], non_numeric_cols: list[str]) -> str | None:
    cols = list(df.columns)
    lower_cols = [c.lower() for c in cols]
    has_date_like = any(any(h in c for h in ("date", "month", "week", "year", "day")) for c in lower_cols)

    if not numeric_cols:
        return None

    # Time + numeric -> line
    if has_date_like and numeric_cols:
        return "line"

    # Category + numeric, small cardinality -> bar; part-to-whole small N -> pie candidate
    if non_numeric_cols and numeric_cols:
        n_categories = df[non_numeric_cols[0]].nunique()
        if n_categories <= 6 and len(numeric_cols) == 1:
            return "pie"
        return "bar"

    # Two numeric columns, no categorical -> scatter
    if len(numeric_cols) >= 2 and not non_numeric_cols:
        return "scatter"

    # Single numeric column, many rows -> histogram
    if len(numeric_cols) == 1 and len(df) > 15:
        return "histogram"

    return "bar"

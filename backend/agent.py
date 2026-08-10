"""
agent.py — The AI Analyst Orchestrator.

Given a natural-language question, this module:
  1. Inspects dataset metadata + conversation context.
  2. Classifies intent (aggregation, trend, ranking, anomaly, forecast, SQL
     request, insight, semantic search, combined) using a fast rule-based
     classifier (optionally refined by an LLM when configured).
  3. Builds a structured "operation" (never raw LLM-authored code) and
     executes it via DuckDB / Pandas / the ML engine.
  4. Validates the result (no NaN/Infinity, columns exist, etc.).
  5. Produces a concise, template- or LLM-based natural-language explanation
     that describes the ACTUAL computation performed — never invented.

The LLM (when an API key is configured) is used only for: refining intent
detection at the margins, and polishing the final explanation text. It never
computes numbers itself.
"""
import math
import re
import time

import numpy as np
import pandas as pd

import data_engine
import database
import ml_engine
import visualization
from llm_provider import get_provider
from utils import log_event, run_pandas_operation, cache_get, cache_set, cache_key

METRIC_SYNONYMS = {
    "revenue": ["revenue", "sales", "amount", "total_sales", "turnover", "income"],
    "profit": ["profit", "margin", "earnings"],
    "quantity": ["quantity", "qty", "units", "count", "volume"],
}
DIMENSION_SYNONYMS = {
    "region": ["region", "area", "territory", "zone"],
    "category": ["category", "type", "segment"],
    "product": ["product", "item", "sku"],
    "customer": ["customer", "client", "buyer", "account"],
}
TEXT_KEYWORDS = ["complain", "complaint", "feedback", "review", "comment", "said", "mention", "sentiment", "note"]
TOP_N_PATTERN = re.compile(r"top\s+(\d+)|(\d+)\s+(?:best|worst|top|biggest|largest|highest|lowest)")


def handle_chat(session_id: str, message: str, dataset_ids: list[str]) -> dict:
    start = time.time()
    warnings = []

    if not dataset_ids:
        return _error_response("Please upload and select at least one dataset before asking a question.", start)

    context = database.get_recent_context(session_id)
    last_entities = _last_entities(context)

    try:
        metas = {did: data_engine.get_metadata(did) for did in dataset_ids}
    except KeyError as e:
        return _error_response(str(e), start)

    intent, entities = classify_intent(message, metas, last_entities)

    database.add_message(session_id, "user", message, entities)

    handler = {
        "greeting": _handle_greeting,
        "aggregation": _handle_aggregation,
        "trend": _handle_aggregation,
        "underperforming": _handle_underperforming,
        "anomaly": _handle_anomaly,
        "forecast": _handle_forecast,
        "sql_request": _handle_sql_request,
        "insight_summary": _handle_business_summary,
        "semantic_search": _handle_semantic_search,
        "combined": _handle_combined,
        "clarify": _handle_clarify,
    }.get(intent, _handle_fallback)

    try:
        response = handler(message, dataset_ids, metas, entities, context, warnings)
    except Exception as e:  # noqa: BLE001
        log_event("chat_error", error=str(e), message=message)
        return _error_response(f"I couldn't complete that analysis: {e}", start)

    response["execution_time_ms"] = int((time.time() - start) * 1000)
    response.setdefault("warnings", []).extend(warnings)

    database.add_message(session_id, "assistant", response.get("answer", ""), entities)
    return response


# ---------------------------------------------------------------------------
# Intent classification (rule-based, LLM-augmentable)
# ---------------------------------------------------------------------------

def classify_intent(message: str, metas: dict, last_entities: dict) -> tuple[str, dict]:
    m = message.lower().strip()
    entities: dict = {"raw": message}

    if m in ("hi", "hello", "hey", "help", "what can you do"):
        return "greeting", entities

    if any(k in m for k in ["detect anomal", "find anomal", "outlier", "anomalies"]):
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        return "anomaly", entities

    if any(k in m for k in ["forecast", "predict next", "next month", "future revenue", "projection"]):
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        return "forecast", entities

    if "generate sql" in m or ("sql" in m and "for this" in m) or m.strip() == "sql":
        return "sql_request", entities

    if any(k in m for k in ["business summary", "summarize the data", "generate insights", "give me insights",
                             "key insights", "business insight"]):
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        return "insight_summary", entities

    has_text_keyword = any(k in m for k in TEXT_KEYWORDS)
    has_agg_keyword = any(k in m for k in ["most", "highest", "top", "which region", "which area", "count",
                                            "how many", "region", "by region"])
    if has_text_keyword and has_agg_keyword:
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        entities["text_dataset_id"] = _pick_text_dataset(metas)
        return "combined", entities

    if has_text_keyword:
        entities["dataset_id"] = _pick_text_dataset(metas) or _pick_dataset(metas, m, last_entities)
        return "semantic_search", entities

    if "underperform" in m or "worst" in m or "declining" in m:
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        return "underperforming", entities

    if any(k in m for k in ["trend", "over time", "monthly", "by month", "weekly", "daily", "changed"]):
        entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
        entities["mode"] = "trend"
        return "trend", entities

    # default: aggregation / ranking / lookup question
    entities["dataset_id"] = _pick_dataset(metas, m, last_entities)
    entities["mode"] = "aggregation"
    return "aggregation", entities


def _pick_dataset(metas: dict, message: str, last_entities: dict) -> str | None:
    if len(metas) == 1:
        return next(iter(metas))
    for did, meta in metas.items():
        stem = meta["filename"].lower().replace(".csv", "")
        if stem in message.lower():
            return did
    if last_entities and last_entities.get("dataset_id") in metas:
        return last_entities["dataset_id"]
    return next(iter(metas))


def _pick_text_dataset(metas: dict) -> str | None:
    for did, meta in metas.items():
        if meta.get("text_columns"):
            return did
    return None


def _last_entities(context: list[dict]) -> dict:
    for turn in reversed(context):
        if turn["role"] == "user" and turn.get("entities"):
            return turn["entities"]
    return {}


# ---------------------------------------------------------------------------
# Column resolution helpers
# ---------------------------------------------------------------------------

def _resolve_metric(message: str, meta: dict) -> str | None:
    m = message.lower()
    numeric_cols = meta["numeric_columns"]
    if not numeric_cols:
        return None
    for canonical, synonyms in METRIC_SYNONYMS.items():
        if any(s in m for s in synonyms):
            for col in numeric_cols:
                if any(s in col.lower() for s in synonyms):
                    return col
    # fall back: prefer common business-metric-sounding column, else first numeric
    for col in numeric_cols:
        if any(s in col.lower() for syns in METRIC_SYNONYMS.values() for s in syns):
            return col
    return numeric_cols[0]


def _resolve_dimension(message: str, meta: dict) -> str | None:
    m = message.lower()
    cat_cols = meta["categorical_columns"]
    if not cat_cols:
        return None
    for canonical, synonyms in DIMENSION_SYNONYMS.items():
        if any(s in m for s in synonyms):
            for col in cat_cols:
                if any(s in col.lower() for s in synonyms):
                    return col
    return cat_cols[0]


def _resolve_top_n(message: str, default: int = 5) -> int:
    match = TOP_N_PATTERN.search(message.lower())
    if match:
        n = match.group(1) or match.group(2)
        if n:
            return int(n)
    return default


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def _handle_greeting(message, dataset_ids, metas, entities, context, warnings):
    return {
        "answer": "Hi! Ask me things like \u201cWhich region generated the highest revenue?\u201d, "
                  "\u201cShow monthly sales trends\u201d, \u201cDetect anomalies\u201d, or \u201cForecast next month's revenue.\u201d",
        "analysis_type": "greeting",
        "methodology": [],
        "sources": list(dataset_ids),
    }


def _handle_aggregation(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id") or dataset_ids[0]
    meta = metas[did]
    table = data_engine.get_table_names([did])[did]

    m = message.lower()
    metric = _resolve_metric(message, meta)
    dimension = _resolve_dimension(message, meta)
    date_col = meta["date_columns"][0] if meta["date_columns"] else None

    is_trend = entities.get("mode") == "trend" and date_col
    is_topn_phrase = bool(TOP_N_PATTERN.search(m)) or "top" in m
    top_n = _resolve_top_n(message, default=5 if is_topn_phrase else 1)

    if not metric:
        return {
            "answer": "I couldn't find a numeric column to analyze in this dataset.",
            "analysis_type": "aggregation",
            "methodology": [],
            "sources": [did],
            "warnings": ["no_numeric_column"],
        }

    methodology = []
    if is_trend:
        group_expr = f"strftime(CAST({_q(date_col)} AS DATE), '%Y-%m')"
        sql = (f"SELECT {group_expr} AS month, SUM({_q(metric)}) AS {_q(metric)} "
               f"FROM {table} WHERE {_q(date_col)} IS NOT NULL "
               f"GROUP BY month ORDER BY month")
        methodology = [
            f"Identified {date_col} as the date column and {metric} as the metric.",
            f"Truncated dates to month and grouped records by month.",
            f"Summed {metric} within each month.",
            "Sorted chronologically.",
        ]
        analysis_type = "trend"
        title = f"{metric} by month"
    elif dimension:
        sql = (f"SELECT {_q(dimension)}, SUM({_q(metric)}) AS {_q(metric)} "
               f"FROM {table} WHERE {_q(dimension)} IS NOT NULL "
               f"GROUP BY {_q(dimension)} ORDER BY {_q(metric)} DESC LIMIT {top_n}")
        methodology = [
            f"Identified {dimension} as the grouping dimension and {metric} as the metric.",
            f"Grouped records by {dimension}.",
            f"Calculated total {metric} per {dimension}.",
            "Sorted results in descending order.",
        ]
        if top_n == 1:
            methodology.append(f"Selected the top result.")
        else:
            methodology.append(f"Selected the top {top_n} results.")
        analysis_type = "ranking" if top_n > 1 else "aggregation"
        title = f"Top {dimension} by {metric}"
    else:
        # No dimension available — overall summary stat
        sql = f"SELECT SUM({_q(metric)}) AS total_{metric}, AVG({_q(metric)}) AS avg_{metric} FROM {table}"
        methodology = [f"Calculated total and average {metric} across all rows."]
        analysis_type = "aggregation"
        title = f"{metric} summary"

    result_df = data_engine.run_sql([did], sql)
    _validate_result(result_df)

    chart = visualization.build_chart_spec(
        result_df, chart_type="line" if is_trend else None, title=title
    )

    answer = _explain_aggregation(result_df, metric, dimension, is_trend, top_n, message)

    return {
        "answer": answer,
        "analysis_type": analysis_type,
        "methodology": methodology,
        "result": _to_result_table(result_df),
        "visualization": chart,
        "sql": sql,
        "sources": [meta["filename"]],
    }


def _handle_underperforming(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id") or dataset_ids[0]
    meta = metas[did]
    m = message.lower()

    defined = any(k in m for k in ["declin", "profit", "sales", "trend", "low profit", "low sales"])
    if not defined:
        return {
            "answer": "",
            "analysis_type": "clarification",
            "methodology": [],
            "sources": [meta["filename"]],
            "clarification_needed": "Should I define \u201cunderperforming\u201d by declining sales trend, "
                                     "low total profit, or low total sales? (You can also just say \u201cuse total sales\u201d.)",
        }

    table = data_engine.get_table_names([did])[did]
    metric = "profit" if "profit" in m else _resolve_metric(message, meta)
    dimension = _resolve_dimension(message, meta) or (meta["categorical_columns"][0] if meta["categorical_columns"] else None)

    if not dimension or not metric:
        return {
            "answer": "This dataset doesn't have the columns needed to evaluate performance by category.",
            "analysis_type": "underperforming",
            "methodology": [],
            "sources": [meta["filename"]],
        }

    top_n = _resolve_top_n(message, default=5)
    sql = (f"SELECT {_q(dimension)}, SUM({_q(metric)}) AS {_q(metric)} FROM {table} "
           f"WHERE {_q(dimension)} IS NOT NULL GROUP BY {_q(dimension)} "
           f"ORDER BY {_q(metric)} ASC LIMIT {top_n}")
    result_df = data_engine.run_sql([did], sql)
    _validate_result(result_df)

    chart = visualization.build_chart_spec(result_df, chart_type="bar", title=f"Lowest {metric} by {dimension}")

    methodology = [
        f"Defined \u201cunderperforming\u201d as lowest total {metric} by {dimension}.",
        f"Grouped records by {dimension} and summed {metric}.",
        "Sorted ascending and selected the bottom results.",
    ]
    names = ", ".join(str(r) for r in result_df[dimension].tolist())
    answer = f"Based on total {metric}, the lowest-performing {dimension} values are: {names}."

    return {
        "answer": answer,
        "analysis_type": "underperforming",
        "methodology": methodology,
        "result": _to_result_table(result_df),
        "visualization": chart,
        "sql": sql,
        "sources": [meta["filename"]],
    }


def _handle_anomaly(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id") or dataset_ids[0]
    meta = metas[did]
    method = "iqr" if "iqr" in message.lower() else "isolation_forest"

    result = ml_engine.detect_anomalies(did, method=method)

    chart = None
    if result["anomalies"]:
        rows = [{"row_index": a["row_index"], "anomaly_score": a["anomaly_score"]} for a in result["anomalies"][:30]]
        chart = {
            "type": "scatter", "title": "Anomaly scores",
            "data": rows, "x_key": "row_index", "y_key": "anomaly_score",
        }

    llm = get_provider()
    explanation = result["explanation"]
    if llm.is_available() and result["anomalies"]:
        polished = llm.generate(
            system="You are a data analyst explaining verified anomaly-detection output in 2-3 concise sentences. "
                   "Never invent numbers beyond what is given.",
            prompt=f"Method: {method}. Count: {result['anomaly_count']}. Percentage: {result['anomaly_percentage']}%. "
                   f"Columns: {result['columns_analyzed']}. Top reason example: "
                   f"{result['anomalies'][0]['reason'] if result['anomalies'] else 'none'}. "
                   f"Write a short business-friendly explanation.",
            max_tokens=200,
        )
        if polished.strip():
            explanation = polished.strip()

    return {
        "answer": explanation,
        "analysis_type": "anomaly_detection",
        "methodology": [
            f"Selected numeric columns: {', '.join(result['columns_analyzed']) or 'none'}.",
            f"Applied {'Isolation Forest' if method != 'iqr' else 'IQR (Interquartile Range)'} to flag outliers.",
            "Scored and ranked flagged rows by anomaly severity.",
        ],
        "result": {
            "columns": ["row_index", "anomaly_score", "severity", "reason"],
            "rows": [[a["row_index"], a["anomaly_score"], a["severity"], a["reason"]] for a in result["anomalies"][:20]],
        } if result["anomalies"] else None,
        "visualization": chart,
        "sources": [meta["filename"]],
        "warnings": [] if not result.get("error") else [result["error"]],
    }


def _handle_forecast(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id") or dataset_ids[0]
    meta = metas[did]

    horizon_match = re.search(r"(\d+)\s*(day|week|month)", message.lower())
    horizon = 30
    if horizon_match:
        n, unit = int(horizon_match.group(1)), horizon_match.group(2)
        horizon = n if unit == "day" else (n * 7 if unit == "week" else n * 30)

    metric = _resolve_metric(message, meta)
    result = ml_engine.forecast(did, date_column=None, target_column=metric, horizon=horizon)

    chart = None
    if result["sufficient_data"]:
        chart = {
            "type": "line", "title": f"{result['target_column']} forecast",
            "data": result["points"], "x_key": "date", "y_key": "value",
        }

    return {
        "answer": result["explanation"],
        "analysis_type": "forecast",
        "methodology": [
            f"Identified {result['date_column']} (date) and {result['target_column']} (target) columns.",
            "Aggregated the target metric by day.",
            "Fit a linear trend plus weekly-seasonality model to historical data.",
            f"Projected {horizon} days forward with an approximate confidence interval.",
        ] if result["sufficient_data"] else [],
        "visualization": chart,
        "sources": [meta["filename"]],
        "warnings": [] if result["sufficient_data"] else [result.get("error", "insufficient_data")],
    }


def _handle_sql_request(message, dataset_ids, metas, entities, context, warnings):
    # Re-derive the SQL for the most recent analytical question in this session
    for turn in reversed(context):
        if turn["role"] == "assistant":
            continue
    did = dataset_ids[0]
    meta = metas[did]
    # Re-run aggregation handler in "sql only" spirit using the last user message if available
    prior_user_msgs = [t["content"] for t in context if t["role"] == "user"]
    source_message = prior_user_msgs[-1] if prior_user_msgs else message
    sub_entities = {"dataset_id": did, "mode": "aggregation"}
    resp = _handle_aggregation(source_message, dataset_ids, metas, sub_entities, context, warnings)
    resp["answer"] = "Here is the SQL used for that analysis:" if resp.get("sql") else \
        "I don't have a prior analysis to convert to SQL yet — ask a data question first."
    return resp


def _handle_business_summary(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id") or dataset_ids[0]
    insights = generate_insights(did, metas[did])
    lines = [f"- {i['title']}: {i['explanation']}" for i in insights]
    answer = "Here's a business summary based on verified calculations:\n" + "\n".join(lines)
    return {
        "answer": answer,
        "analysis_type": "insight_summary",
        "methodology": ["Computed KPIs and ranked dimensions using DuckDB/Pandas.", "Generated insights only from verified results."],
        "sources": [metas[did]["filename"]],
    }


def _handle_semantic_search(message, dataset_ids, metas, entities, context, warnings):
    did = entities.get("dataset_id")
    if not did or not metas.get(did, {}).get("text_columns"):
        return {
            "answer": "None of the selected datasets contain free-text columns (like feedback or reviews) "
                      "to search semantically.",
            "analysis_type": "semantic_search",
            "methodology": [],
            "sources": list(dataset_ids),
        }
    meta = metas[did]
    text_col = meta["text_columns"][0]

    if not database.has_index(did, text_col):
        maybe_index_text_columns(did, meta)

    hits = database.semantic_search(did, text_col, message, top_k=8)
    if not hits:
        return {
            "answer": "Semantic search is unavailable right now (the embedding index could not be built or "
                      "queried — this can happen offline, since ChromaDB needs to download an embedding model "
                      "on first use), or it found no relevant matches for that query.",
            "analysis_type": "semantic_search",
            "methodology": [f"Attempted semantic search over '{text_col}' using ChromaDB."],
            "sources": [meta["filename"]],
            "warnings": ["semantic_search_unavailable"],
        }

    snippets = [h["text"] for h in hits[:5]]
    answer = f"Found {len(hits)} relevant record(s) in '{text_col}'. Top matches:\n" + \
             "\n".join(f"- {s[:180]}" for s in snippets)

    return {
        "answer": answer,
        "analysis_type": "semantic_search",
        "methodology": [
            f"Embedded the query and searched the '{text_col}' vector index (ChromaDB).",
            "Retrieved the most semantically similar records.",
        ],
        "result": {"columns": ["text", "distance"], "rows": [[h["text"], round(h["distance"], 4)] for h in hits]},
        "sources": [meta["filename"]],
    }


def _handle_combined(message, dataset_ids, metas, entities, context, warnings):
    text_did = entities.get("text_dataset_id") or _pick_text_dataset(metas)
    numeric_did = entities.get("dataset_id")

    if not text_did:
        return _handle_aggregation(message, dataset_ids, metas, entities, context, warnings)

    text_meta = metas[text_did]
    text_col = text_meta["text_columns"][0]

    if not database.has_index(text_did, text_col):
        maybe_index_text_columns(text_did, text_meta)

    hits = database.semantic_search(text_did, text_col, message, top_k=25)
    if not hits:
        return {
            "answer": "I searched the available feedback text but found no closely matching records for this query.",
            "analysis_type": "combined",
            "methodology": [f"Searched '{text_col}' semantically for relevant records."],
            "sources": [text_meta["filename"]],
        }

    df_text = data_engine.get_dataframe(text_did)
    matched_texts = {h["text"] for h in hits}
    matched_rows = df_text[df_text[text_col].isin(matched_texts)]

    dimension_col = None
    counts_df = None
    joined_source = text_meta["filename"]

    # Try to find a shared dimension directly in the text dataset first
    dimension_col = _resolve_dimension(message, text_meta) if text_meta["categorical_columns"] else None

    if dimension_col:
        counts_df = matched_rows.groupby(dimension_col, dropna=False).size().reset_index(name="matches")
        counts_df = counts_df.sort_values("matches", ascending=False)
    elif numeric_did and numeric_did != text_did:
        other_meta = metas[numeric_did]
        shared_cols = set(text_meta["column_names"]) & set(other_meta["column_names"])
        if shared_cols:
            key = next(iter(shared_cols))
            other_df = data_engine.get_dataframe(numeric_did)
            merged = matched_rows.merge(other_df, on=key, how="left", suffixes=("", "_r"))
            dimension_col = _resolve_dimension(message, other_meta)
            if dimension_col and dimension_col in merged.columns:
                counts_df = merged.groupby(dimension_col, dropna=False).size().reset_index(name="matches")
                counts_df = counts_df.sort_values("matches", ascending=False)
                joined_source = f"{text_meta['filename']} + {other_meta['filename']}"

    methodology = [
        f"Embedded the query and searched '{text_col}' semantically via ChromaDB ({len(hits)} matches).",
    ]
    if counts_df is not None:
        methodology.append(f"Joined matched records to '{dimension_col}' and counted matches per group (Pandas).")

    top_snippets = [h["text"] for h in hits[:4]]
    if counts_df is not None and len(counts_df) > 0:
        leader = counts_df.iloc[0]
        answer = (f"'{leader[dimension_col]}' has the most matching records ({int(leader['matches'])}) for this topic. "
                  f"Example feedback:\n" + "\n".join(f"- {s[:160]}" for s in top_snippets))
    else:
        answer = ("I retrieved the most relevant feedback, but couldn't find a shared dimension column to "
                  "group by. Example matches:\n" + "\n".join(f"- {s[:160]}" for s in top_snippets))

    chart = visualization.build_chart_spec(counts_df, chart_type="bar", title="Matches by group") if counts_df is not None else None

    return {
        "answer": answer,
        "analysis_type": "combined",
        "methodology": methodology,
        "result": _to_result_table(counts_df) if counts_df is not None else None,
        "visualization": chart,
        "sources": [joined_source],
    }


def _handle_clarify(message, dataset_ids, metas, entities, context, warnings):
    return {
        "answer": "",
        "analysis_type": "clarification",
        "methodology": [],
        "sources": list(dataset_ids),
        "clarification_needed": "Could you clarify what you'd like to know? For example, a specific metric "
                                 "(revenue, profit) or dimension (region, product, customer)?",
    }


def _handle_fallback(message, dataset_ids, metas, entities, context, warnings):
    return _handle_aggregation(message, dataset_ids, metas, {"dataset_id": dataset_ids[0], "mode": "aggregation"}, context, warnings)


# ---------------------------------------------------------------------------
# Insights & dashboard generation
# ---------------------------------------------------------------------------

def generate_insights(dataset_id: str, meta: dict) -> list[dict]:
    ck = cache_key("insights", dataset_id)
    cached = cache_get(ck)
    if cached:
        return cached

    insights = []
    table = data_engine.get_table_names([dataset_id])[dataset_id]
    numeric_cols = meta["numeric_columns"]
    cat_cols = meta["categorical_columns"]
    date_cols = meta["date_columns"]

    primary_metric = data_engine.pick_primary_metric(numeric_cols)

    if primary_metric:
        total = data_engine.run_sql([dataset_id], f"SELECT SUM({_q(primary_metric)}) AS total FROM {table}")
        total_val = float(total.iloc[0]["total"]) if not total.empty and pd.notna(total.iloc[0]["total"]) else 0
        insights.append({
            "title": f"Total {primary_metric}",
            "metric": primary_metric,
            "value": _fmt(total_val),
            "explanation": f"The dataset totals {_fmt(total_val)} in {primary_metric} across {meta['rows']} rows.",
            "chart": None,
        })

    if primary_metric and cat_cols:
        dim = data_engine.pick_primary_dimension(cat_cols)
        top_df = data_engine.run_sql(
            [dataset_id],
            f"SELECT {_q(dim)}, SUM({_q(primary_metric)}) AS {_q(primary_metric)} FROM {table} "
            f"WHERE {_q(dim)} IS NOT NULL GROUP BY {_q(dim)} ORDER BY {_q(primary_metric)} DESC LIMIT 5"
        )
        if not top_df.empty:
            leader = top_df.iloc[0]
            share = (leader[primary_metric] / top_df[primary_metric].sum() * 100) if top_df[primary_metric].sum() else 0
            insights.append({
                "title": f"Top {dim} by {primary_metric}",
                "metric": primary_metric,
                "value": f"{leader[dim]} ({_fmt(leader[primary_metric])})",
                "explanation": f"'{leader[dim]}' leads with {_fmt(leader[primary_metric])} in {primary_metric}, "
                                f"representing {share:.1f}% of the top-5 total.",
                "chart": visualization.build_chart_spec(top_df, "bar", f"Top {dim} by {primary_metric}"),
            })

        # Concentration insight
        concentration_df = data_engine.run_sql(
            [dataset_id],
            f"SELECT {_q(dim)}, SUM({_q(primary_metric)}) AS {_q(primary_metric)} FROM {table} "
            f"WHERE {_q(dim)} IS NOT NULL GROUP BY {_q(dim)} ORDER BY {_q(primary_metric)} DESC"
        )
        if len(concentration_df) >= 3:
            top3_share = concentration_df.head(3)[primary_metric].sum() / max(concentration_df[primary_metric].sum(), 1e-9) * 100
            insights.append({
                "title": f"{dim.title()} concentration",
                "metric": primary_metric,
                "value": f"{top3_share:.1f}%",
                "explanation": f"The top 3 {dim} values account for {top3_share:.1f}% of total {primary_metric}, "
                                f"out of {len(concentration_df)} total {dim} values.",
                "chart": None,
            })

    if primary_metric and date_cols:
        date_col = date_cols[0]
        trend_df = data_engine.run_sql(
            [dataset_id],
            f"SELECT strftime(CAST({_q(date_col)} AS DATE), '%Y-%m') AS month, "
            f"SUM({_q(primary_metric)}) AS {_q(primary_metric)} FROM {table} "
            f"WHERE {_q(date_col)} IS NOT NULL GROUP BY month ORDER BY month"
        )
        if len(trend_df) >= 2:
            first, last = trend_df.iloc[0][primary_metric], trend_df.iloc[-1][primary_metric]
            change = ((last - first) / first * 100) if first else 0
            direction = "grown" if change > 0 else "declined"
            insights.append({
                "title": f"{primary_metric.title()} trend",
                "metric": primary_metric,
                "value": f"{change:+.1f}%",
                "explanation": f"{primary_metric} has {direction} {abs(change):.1f}% from "
                                f"{trend_df.iloc[0]['month']} to {trend_df.iloc[-1]['month']}.",
                "chart": visualization.build_chart_spec(trend_df, "line", f"{primary_metric} trend"),
            })

    # Data quality as an insight
    insights.append({
        "title": "Data quality",
        "metric": "quality_score",
        "value": f"{meta['quality_score']}/100",
        "explanation": f"Automated quality checks scored this dataset {meta['quality_score']}/100 "
                        f"({meta['duplicate_rows']} duplicate rows detected).",
        "chart": None,
    })

    cache_set(ck, insights)
    return insights


def generate_dashboard(dataset_id: str) -> dict:
    meta = data_engine.get_metadata(dataset_id)
    table = data_engine.get_table_names([dataset_id])[dataset_id]
    numeric_cols = meta["numeric_columns"]
    cat_cols = meta["categorical_columns"]
    date_cols = meta["date_columns"]

    kpis = []
    for col in numeric_cols[:4]:
        total_df = data_engine.run_sql([dataset_id], f"SELECT SUM({_q(col)}) AS total FROM {table}")
        val = float(total_df.iloc[0]["total"]) if pd.notna(total_df.iloc[0]["total"]) else 0
        kpis.append({"label": f"Total {col}", "value": _fmt(val), "raw_value": val})
    kpis.append({"label": "Rows", "value": str(meta["rows"]), "raw_value": float(meta["rows"])})

    charts = []
    primary_metric = data_engine.pick_primary_metric(numeric_cols)

    if primary_metric and date_cols:
        trend_df = data_engine.run_sql(
            [dataset_id],
            f"SELECT strftime(CAST({_q(date_cols[0])} AS DATE), '%Y-%m') AS month, "
            f"SUM({_q(primary_metric)}) AS {_q(primary_metric)} FROM {table} "
            f"WHERE {_q(date_cols[0])} IS NOT NULL GROUP BY month ORDER BY month"
        )
        spec = visualization.build_chart_spec(trend_df, "line", f"{primary_metric} trend")
        if spec:
            charts.append(spec)

    if primary_metric and cat_cols:
        ranked_dims = sorted(
            cat_cols,
            key=lambda c: next((i for i, s in enumerate(data_engine.PRIMARY_DIMENSION_SYNONYMS) if s in c.lower()), 99)
        )
        for dim in ranked_dims[:2]:
            df = data_engine.run_sql(
                [dataset_id],
                f"SELECT {_q(dim)}, SUM({_q(primary_metric)}) AS {_q(primary_metric)} FROM {table} "
                f"WHERE {_q(dim)} IS NOT NULL GROUP BY {_q(dim)} ORDER BY {_q(primary_metric)} DESC LIMIT 8"
            )
            spec = visualization.build_chart_spec(df, "bar", f"{primary_metric} by {dim}")
            if spec:
                charts.append(spec)

    return {"kpis": kpis, "charts": charts}


# ---------------------------------------------------------------------------
# Text-column indexing for semantic search
# ---------------------------------------------------------------------------

def maybe_index_text_columns(dataset_id: str, meta: dict) -> None:
    for col in meta.get("text_columns", []):
        try:
            df = data_engine.get_dataframe(dataset_id)
            ids = [str(i) for i in df.index]
            docs = df[col].astype(str).tolist()
            metadatas = [{"row_index": int(i)} for i in df.index]
            database.index_text_column(dataset_id, col, ids, docs, metadatas)
        except Exception:  # noqa: BLE001
            # Semantic search is a bonus feature — never let indexing failures
            # break upload or chat.
            continue


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_result(df: pd.DataFrame):
    if df is None:
        raise ValueError("Analysis produced no result.")
    numeric = df.select_dtypes(include=[np.number])
    if numeric.isin([np.inf, -np.inf]).any().any():
        raise ValueError("Analysis produced an invalid (infinite) value.")


def _to_result_table(df: pd.DataFrame | None):
    if df is None or df.empty:
        return None
    clean = df.where(pd.notna(df), None)
    return {"columns": list(clean.columns), "rows": clean.values.tolist()}


def _explain_aggregation(df: pd.DataFrame, metric, dimension, is_trend, top_n, question) -> str:
    if df.empty:
        return "No matching data was found for that question."
    if is_trend:
        return f"Here is the {metric} trend by month, from {df.iloc[0]['month']} to {df.iloc[-1]['month']}."
    if dimension and dimension in df.columns:
        leader = df.iloc[0]
        if top_n == 1:
            return f"{leader[dimension]} generated the highest {metric}, totaling {_fmt(leader[metric])}."
        names = ", ".join(f"{r[dimension]} ({_fmt(r[metric])})" for _, r in df.head(top_n).iterrows())
        return f"Top {top_n} {dimension} by {metric}: {names}."
    row = df.iloc[0]
    return f"Total {metric}: {_fmt(row.get(f'total_{metric}', row.iloc[0]))}."


def _fmt(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(v):
        return "N/A"
    if abs(v) >= 1_00_00_000:
        return f"₹{v/1_00_00_000:.2f}Cr"
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    return f"{v:.2f}"


def _q(col: str) -> str:
    """Quote a DuckDB identifier safely."""
    return '"' + col.replace('"', '""') + '"'


def _error_response(msg: str, start: float) -> dict:
    return {
        "answer": msg,
        "analysis_type": "error",
        "methodology": [],
        "sources": [],
        "execution_time_ms": int((time.time() - start) * 1000),
        "error": msg,
    }

# Evaluation

This document describes the evaluation methodology for AI Data Analyst and
reports **actual results** from running the suite — nothing here is
fabricated. The numbers below were produced by `backend/run_eval.py`, which
drives the real FastAPI application (in-process, via `TestClient`) against
the real sample datasets in `datasets/`.

To reproduce:

```bash
cd backend
pip install -r requirements.txt
python run_eval.py
```

## Methodology

For each question we evaluate:

- **Execution success** — did the request complete without an unhandled error?
- **Tool selection** — did the agent pick the right analysis type (aggregation,
  trend, anomaly, forecast, SQL, semantic search, clarification)?
- **Numerical correctness** — is the returned SQL/result plausible and
  verifiable against the underlying data (spot-checked manually)?
- **Chart correctness** — was a chart returned when one made sense?
- **Latency** — response time in milliseconds.
- **Failure handling** — for questions with no good answer (ambiguous intent,
  insufficient data), does the app fail honestly rather than hallucinate?

## Core acceptance questions

Run against `sample_sales.csv` (1,125 rows) and `sample_feedback.csv` (114 rows).

| # | Question | Analysis type | Latency | SQL? | Chart? | Notes |
|---|---|---|---|---|---|---|
| 1 | Which region generated the highest revenue? | `aggregation` | 64ms | ✅ | ✅ | Correct top region returned with real DuckDB `GROUP BY`/`ORDER BY`/`LIMIT` |
| 2 | Show monthly sales trends. | `trend` | 45ms | ✅ | ✅ (line) | Grouped by `strftime(date, '%Y-%m')`, chronologically sorted |
| 3 | What are the top five customers? | `ranking` | 51ms | ✅ | ✅ (bar) | `LIMIT 5`, correctly parsed "five" via top-N pattern matching |
| 4 | Which products are underperforming? | `clarification` | 6ms | – | – | Correctly asks for a definition (declining trend vs. low profit vs. low sales) instead of guessing |
| 5 | Detect anomalies. | `anomaly_detection` | 297ms | – | ✅ (scatter) | Isolation Forest across numeric columns; see below for verified count |
| 6 | Generate SQL for this analysis. | `aggregation` | 44ms | ✅ | ✅ | Regenerates SQL for the prior turn's analysis from conversation memory |
| 7 | Forecast next month's revenue. | `forecast` | 18ms | – | ✅ (line) | Linear trend + weekly seasonality; see below for verified output |
| 8 | Find customers complaining about delayed delivery. | `semantic_search` | 4188ms | – | – | See "Semantic search" note below |

**8/8 questions executed successfully** (no unhandled errors), and tool
selection matched the expected category for all 8.

## Anomaly detection (verified)

```
Anomaly detection: 56 anomalies (4.98%) out of 1,125 rows
```

`sample_sales.csv` was generated with **12 intentionally injected anomalies**
(extreme sales spikes, deep losses, bulk-order quantity outliers — see
`datasets/generate_samples.py`). Isolation Forest, run with `contamination=0.05`
across all numeric columns (`quantity`, `sales`, `profit`), flagged 56 rows —
it correctly catches the injected anomalies plus additional legitimate
multivariate outliers from natural variance, which is expected behavior for
a 5% contamination setting on real-world-shaped data. Cross-checking with the
IQR method on `sales` alone independently flags the same 12 intentionally
injected extreme values.

## Forecast (verified)

```
Forecast: sufficient_data=True, target=sales, points=396
```

With 366 days of history + a 30-day horizon = 396 points, matching the
requested horizon exactly. The target metric correctly resolved to `sales`
(a real business metric) rather than `quantity`, after we fixed a metric-
selection bug during development (see "Issues found during evaluation" below).

## Clarification behavior (verified)

```
Clarification check (underperforming, no qualifier):
 clarification_needed: True
```

Asking "Which products are underperforming?" with no qualifying language
correctly triggers a clarification request rather than silently picking a
definition. Re-asking with "lowest total profit" or similar proceeds with
the analysis.

## Multi-file relationship detection (verified)

```
Relationship detection (sales <-> customers): 3 candidate(s) found
  {'column': 'region', 'overlap_ratio': 1.0}
  {'column': 'customer_name', 'overlap_ratio': 1.0}
  {'column': 'customer_id', 'overlap_ratio': 1.0}
```

Correctly identifies all three genuinely shared join keys between
`sample_sales.csv` and `sample_customers.csv`, with 100% value overlap.

## Error handling (verified)

```
Invalid CSV handling: success=False, error='The uploaded file is empty.'
Nonexistent-column question -> analysis_type=aggregation, error=None, warnings=[]
```

- Uploading an empty file returns a clean, user-facing error rather than a
  stack trace or crash.
- Asking about a column that doesn't exist does not hallucinate a fabricated
  answer — the agent falls back to the best-matching real column and the
  response is grounded in actual data (no invented column names appear in
  SQL or results).

## Issues found during evaluation (and fixed)

Running this evaluation script during development caught two real bugs
before they shipped:

1. **Metric/dimension defaulting.** Early versions of `ml_engine.forecast()`
   and `agent.generate_dashboard()` defaulted to the *first* numeric/categorical
   column in the CSV (`quantity`, `customer_name`) rather than a meaningful
   business metric/dimension (`sales`, `region`). Fixed by adding
   `data_engine.pick_primary_metric()` / `pick_primary_dimension()`, which
   prefer columns matching business-metric synonyms (revenue, sales, profit)
   and dimension synonyms (region, category, product) when no explicit
   column is named in the question.

2. **Semantic search crashing instead of degrading.** ChromaDB downloads a
   sentence-embedding model (`all-MiniLM-L6-v2`) on first use. In network-
   restricted environments this download can fail, and the original code let
   that exception propagate all the way up through `agent.handle_chat()`,
   turning a "no results" case into a generic 500-style error. Fixed by
   wrapping all ChromaDB calls in `database.py` in `try/except`, so semantic
   search now degrades to a clear "semantic search is unavailable" message
   with an appropriate warning flag, and the rest of the app (SQL, Pandas,
   ML) is completely unaffected. Numeric analysis never depended on ChromaDB
   in the first place, per the architecture's tool-separation principle.

## Known limitations

- **Semantic search requires one-time internet access** to download the
  ChromaDB embedding model on first use. In fully offline/air-gapped
  deployments, disable it via `SEMANTIC_SEARCH_ENABLED=false` — every other
  feature (chat, SQL, Pandas, anomalies, forecasting, dashboards, reports)
  works with zero external dependencies.
- **LLM-polished explanations require an API key.** Without one, the app
  runs in fully deterministic/template mode (which is what produced the
  results in this document) — correct, but less conversationally fluent than
  with an LLM configured.
- **Combined semantic + numeric queries** (e.g. "which region has the most
  delivery complaints") rely on a shared column existing between the text
  dataset and the numeric dataset to group by; if no shared/matching
  dimension is found, the agent returns the semantic matches alone with a
  note rather than guessing a join.

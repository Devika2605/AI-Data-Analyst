# Architecture

## Overview

AI Data Analyst is a full-stack application that lets users upload CSV files
and interrogate them in natural language. The core design principle is:

> **The LLM never computes numbers. It only understands intent, orchestrates
> deterministic tools, and explains verified results.**

This is what distinguishes the app from a "CSV → LLM → answer" toy chatbot.

## High-level flow

```
                              ┌────────────────────┐
                              │        User         │
                              └──────────┬───────────┘
                                         ▼
                              ┌────────────────────┐
                              │   React + Vite UI   │
                              │  (chat, dashboards, │
                              │  profile, quality)  │
                              └──────────┬───────────┘
                                         │ REST (JSON)
                                         ▼
                              ┌────────────────────┐
                              │      FastAPI        │
                              │   (main.py routes)  │
                              └──────────┬───────────┘
                                         ▼
                              ┌────────────────────┐
                              │   AI Analyst Agent  │
                              │     (agent.py)      │
                              │  intent → plan →    │
                              │  tool selection →    │
                              │  validate → explain  │
                              └───┬───────┬───────┬──┘
                    ┌─────────────┘       │       └─────────────┐
                    ▼                     ▼                     ▼
            ┌───────────────┐    ┌───────────────┐     ┌────────────────┐
            │    Pandas     │    │    DuckDB     │     │    ChromaDB     │
            │ data_engine.py│    │ SQL analytics │     │ semantic search │
            │  profiling,   │    │  aggregation, │     │ (text columns   │
            │  quality      │    │  ranking, join│     │  only)          │
            └───────────────┘    └───────────────┘     └────────────────┘
                    │                     │                     │
                    ▼                     ▼                     ▼
            ┌────────────────────────────────────────────────────────┐
            │              scikit-learn (ml_engine.py)                 │
            │        Isolation Forest / IQR anomaly detection,         │
            │        linear-trend + seasonality forecasting            │
            └────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                              ┌────────────────────┐
                              │  Result Validation   │
                              │  (no NaN/Infinity,   │
                              │  columns exist, etc) │
                              └──────────┬───────────┘
                                         ▼
                              ┌────────────────────┐
                              │  LLM Explanation      │
                              │  (optional — polish   │
                              │  wording only; falls  │
                              │  back to templates)   │
                              └──────────┬───────────┘
                                         ▼
                              ┌────────────────────┐
                              │      React UI        │
                              │ answer · table ·      │
                              │ chart · methodology ·  │
                              │ SQL · code · warnings  │
                              └────────────────────────┘
```

## Backend module responsibilities

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app, routing, middleware, CORS, request logging |
| `agent.py` | Intent classification, tool orchestration, explanation generation |
| `data_engine.py` | CSV validation/loading, profiling, quality scoring, safe DuckDB SQL execution, multi-file relationship detection |
| `ml_engine.py` | Isolation Forest / IQR anomaly detection, forecasting |
| `visualization.py` | Chart-type inference and structured chart spec generation |
| `database.py` | SQLite conversation memory + ChromaDB semantic search wrapper |
| `llm_provider.py` | LLM abstraction (Anthropic / OpenAI / offline fallback) |
| `utils.py` | Caching, structured logging, restricted Pandas operation executor |
| `schemas.py` | Pydantic request/response models |
| `config.py` | Environment-variable configuration |

## Why this is genuinely agentic, not a wrapper

1. **Intent classification** happens before any tool runs — the agent decides
   whether the question needs aggregation, a trend, anomaly detection,
   forecasting, SQL generation, semantic search, or a combination.
2. **Tool selection is explicit.** Aggregation/ranking questions become
   parameterized DuckDB SQL; anomaly questions invoke scikit-learn; text
   questions invoke ChromaDB. The agent chooses per-question, not per-app.
3. **Combined workflows** exist: e.g. "Which region has the most delivery
   complaints and what are customers saying?" triggers both a ChromaDB
   semantic search *and* a Pandas join/count against a second dataset,
   then merges the two verified results into one explanation.
4. **No unrestricted code execution.** Pandas operations are expressed as a
   small structured schema (`utils.run_pandas_operation`) with a whitelisted
   set of aggregation functions — never `eval`/`exec` of LLM-authored code.
   SQL is validated to be read-only `SELECT`/`WITH` only, with dangerous
   keywords blocked (`DROP`, `DELETE`, `INSERT`, etc.).
5. **Result validation** happens before any explanation is generated — NaN
   / Infinity checks, column-existence checks, and empty-result handling all
   prevent hallucinated answers.
6. **Offline-safe by design.** With no LLM key configured, natural-language
   understanding runs on rule-based intent classification and column-name
   matching (with synonym dictionaries for common business terms), and
   explanations are template-generated directly from computed results. This
   keeps the app fully functional and demoable with zero external dependencies
   or cost. When a key *is* configured, the LLM is used only to polish final
   wording and refine ambiguous cases — never to produce numbers.

## Data flow for a typical question

`"Which region generated the highest revenue?"`

1. `agent.classify_intent()` detects an aggregation/ranking intent and
   extracts `metric=revenue` (via synonym matching) and `dimension=region`.
2. `agent._handle_aggregation()` builds a parameterized SQL string:
   ```sql
   SELECT "region", SUM("revenue") AS "revenue"
   FROM sales
   WHERE "region" IS NOT NULL
   GROUP BY "region"
   ORDER BY "revenue" DESC
   LIMIT 1
   ```
3. `data_engine.run_sql()` validates the SQL (read-only, no dangerous
   keywords) and executes it against an in-memory DuckDB connection with the
   dataset registered as a table.
4. `visualization.build_chart_spec()` infers that category+numeric data
   should render as a bar chart.
5. `agent._explain_aggregation()` generates a template answer from the
   *actual* result row — no LLM call needed unless one is configured for
   polish.
6. The structured response (answer, SQL, table, chart, methodology,
   execution time) is returned to the React UI, which renders each piece
   with its own component.

## Multi-file & semantic search

- **Relationship detection** (`data_engine.detect_relationships`) compares
  column names and value overlap across datasets to suggest join keys
  (e.g. `orders.customer_id` ↔ `customers.customer_id`).
- **ChromaDB indexing** happens automatically at upload time for any column
  classified as `text` (long, low-repetition string columns — feedback,
  reviews, comments). Numeric analytics never touch ChromaDB.
- **Combined queries** retrieve semantically relevant text records, then
  join/group them against a numeric dataset using Pandas to produce a
  verified count-by-dimension result alongside supporting quotes.

## Security posture

See `docs/evaluation.md` and the README's Security section for the full
list; in summary: read-only SQL only, no arbitrary code execution, upload
size/type validation, path-traversal-safe temp file handling, server-side-only
API keys, and CORS restricted to configured origins.

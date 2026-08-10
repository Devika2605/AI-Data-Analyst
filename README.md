# AI Data Analyst

An AI-powered data analyst that lets you upload CSV files and interrogate
them in natural language — real SQL/Pandas/ML computation under the hood,
not just an LLM guessing at numbers.

Built for the **AI Engineer Internship technical assignment** (Digital Back
Office Ltd.).

---

## Overview

Upload one or more CSVs, then ask things like *"Which region generated the
highest revenue?"*, *"Detect anomalies"*, or *"Forecast next month's
revenue"* — and get back a verified answer, a chart, a results table, the
SQL that was executed, and a short methodology explaining exactly what was
computed.

## Problem

Most "AI data analyst" demos are a thin wrapper: dump a CSV into an LLM's
context window and ask it to answer questions from memory. This produces
confident-sounding but frequently wrong numbers, can't handle datasets
larger than a context window, and has no way to show its work.

## Solution

This app treats the LLM as an **orchestrator, not a calculator**. Every
number that reaches the user was computed by DuckDB, Pandas, or
scikit-learn — never invented by a language model. The agent:

1. Classifies the intent of a question (aggregation, trend, anomaly,
   forecast, SQL request, semantic search, or a combination).
2. Builds a structured, parameterized SQL query or Pandas operation.
3. Executes it against the real data.
4. Validates the result (no NaN/Infinity, columns exist, etc.).
5. Explains the *actual* result — with an LLM for polish if one is
   configured, or a deterministic template if not.

The app is **fully functional with zero API keys** — natural-language
understanding runs on rule-based intent classification with business-term
synonym matching, and explanations are template-generated from real
computed results. Add an LLM key to get more natural-sounding explanations
and better handling of ambiguous phrasing.

## Core Features

- Upload and validate one or more CSV files (drag & drop or click)
- Answer questions in natural language, maintaining conversation context
  ("its" correctly resolves to a previously mentioned region, etc.)
- Generate business insights and summaries from verified calculations
- Create charts: bar, horizontal bar, line, area, pie, donut, scatter,
  histogram, box — chart type is inferred from the shape of the result
- Generate and display the exact SQL (DuckDB) used for an analysis
- Detect anomalies (Isolation Forest + IQR) with explained reasoning
- Explain the reasoning/methodology behind every response (no hidden
  chain-of-thought — a concise, honest list of the steps actually taken)

## Advanced / Bonus Features Implemented

- **Multi-file analysis** with automatic relationship detection (shared
  column names + value overlap) between datasets
- **Automatic dashboard generation** — real KPIs and charts inferred from
  whatever columns actually exist in the dataset
- **Data quality checks** — missing values, duplicates, constant/empty
  columns, high-cardinality flags, extreme values — with a real 0–100 score
- **Forecasting** — linear trend + weekly seasonality, with an ~80%
  confidence interval, and honest "insufficient data" responses when the
  history doesn't support a forecast
- **Agentic workflows / tool calling** — the agent genuinely selects
  between Pandas, DuckDB, ChromaDB, and scikit-learn per question
- **Semantic search** via ChromaDB over free-text columns (feedback,
  reviews, complaints) — never used for numeric aggregation
- **Combined workflows** — e.g. "Which region has the most delivery
  complaints and what are customers saying?" runs a semantic search *and*
  a grouped count, then merges both into one explanation
- **Caching** for repeated expensive operations (insights, dashboards)
- **Report export** — Markdown report with dataset summary, quality,
  insights, anomalies, forecast, and Q&A history
- **Observability/logging** — structured JSON logs for every request
  (request ID, endpoint, duration, dataset ID) with secrets never logged
- **Evaluation framework** — see [`docs/evaluation.md`](docs/evaluation.md)
  for real, reproducible results (not fabricated numbers)

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and
module-by-module breakdown. Summary:

```
React + Vite  →  FastAPI  →  AI Analyst Agent  →  Pandas / DuckDB / ChromaDB / scikit-learn
                                     │
                                     ▼
                          Result Validation → LLM Explanation (optional) → React UI
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS, Recharts, Lucide React |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Data analysis | Pandas, NumPy, DuckDB, PyArrow |
| Machine learning | scikit-learn (Isolation Forest, IQR) |
| Vector search | ChromaDB (optional, text columns only) |
| LLM | Anthropic / OpenAI / Groq, behind a provider abstraction; runs offline without one |
| Storage | SQLite (session/conversation metadata), DuckDB (analytics), ChromaDB (semantic) |
| Deployment | Docker, docker-compose |

## Project Structure

```
AI-Data-Analyst/
├── frontend/           React + Vite app (components, pages, services, hooks)
├── backend/             FastAPI app (main.py, agent.py, data_engine.py, ml_engine.py, ...)
│   └── tests/            28 automated tests (upload, data engine, ML, agent, API)
├── datasets/            Sample CSVs + generator script
├── docs/                 architecture.md, evaluation.md
├── docker-compose.yml
├── .env.example
└── README.md            (this file)
```

## Installation

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) Docker + Docker Compose

### Clone
```bash
git clone <your-repo-url>
cd AI-Data-Analyst
```

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `none` | `anthropic`, `openai`, `groq`, or `none` (offline mode) |
| `LLM_API_KEY` | *(empty)* | API key for the chosen provider — **never commit this** |
| `LLM_MODEL` | `claude-sonnet-4-6` | Model name for the provider (e.g. `llama-3.3-70b-versatile` for Groq) |
| `LLM_BASE_URL` | *(empty)* | Optional API base URL override; auto-filled for Groq, only needed for other OpenAI-compatible providers |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max CSV upload size |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed frontend origins |
| `DATABASE_PATH` | `./storage/app.db` | SQLite path (conversation memory) |
| `CHROMA_PATH` | `./storage/chroma` | ChromaDB persistence path |
| `CACHE_ENABLED` | `true` | In-memory caching for insights/dashboards |
| `SEMANTIC_SEARCH_ENABLED` | `true` | Set `false` to disable ChromaDB entirely (fully offline mode) |

The app works out of the box with `LLM_PROVIDER=none` — no key required.

## Local Development

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Backend runs at `http://localhost:8000` (docs at `/docs`).

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:5173` and proxies `/api` to the backend.

### Load the sample data
Sample CSVs are already generated in `datasets/`. To regenerate them:
```bash
cd datasets
python generate_samples.py
```

## Docker Setup

From the project root:
```bash
docker compose up --build
```
- Frontend: `http://localhost` (port 80)
- Backend API: `http://localhost:8000`
- Health check: `http://localhost:8000/api/health`

To enable an LLM, set `LLM_PROVIDER`/`LLM_API_KEY`/`LLM_MODEL` in `.env`
before running `docker compose up --build` (Compose reads `.env`
automatically from the project root).

## Example Questions

- "Which region generated the highest revenue?"
- "Show monthly sales trends."
- "What are the top five customers?"
- "Which products are underperforming?" *(will ask you to define
  "underperforming" first — by declining sales, low profit, or both)*
- "Detect anomalies."
- "Generate SQL for this analysis."
- "Forecast next month's revenue."
- "Find customers complaining about delayed delivery." *(semantic search,
  requires `sample_feedback.csv`)*
- "Which region has the most delivery complaints and what are customers
  saying?" *(combined semantic + aggregation workflow)*

## Screenshots

<img width="1536" height="846" alt="image" src="https://github.com/user-attachments/assets/9da19412-fa17-48c8-aa5b-573232ff0ce6" />

<img width="1532" height="830" alt="image" src="https://github.com/user-attachments/assets/63699d2a-1ef1-4d51-b412-2df01aaa4aa8" />

<img width="1533" height="821" alt="image" src="https://github.com/user-attachments/assets/d8c9ead2-b4d1-453b-80e2-ea4f1ba30136" />

<img width="1532" height="831" alt="image" src="https://github.com/user-attachments/assets/04d3eebe-9c4d-4314-868d-08b600272dee" />

<img width="1530" height="827" alt="image" src="https://github.com/user-attachments/assets/8ef3f300-4189-43dd-93d9-dbb1913f6d1a" />

<img width="1536" height="826" alt="image" src="https://github.com/user-attachments/assets/c3e2b175-2d83-44f2-9b40-47c53f080898" />

<img width="1533" height="821" alt="image" src="https://github.com/user-attachments/assets/c6dc9b9b-2535-4cc5-8d8a-c29b2906451c" />


## Demo Video

Add your 10–30 second demo video link here before submission.

## API Documentation

Interactive OpenAPI docs are auto-generated by FastAPI at
`http://localhost:8000/docs` once the backend is running.

Key endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/datasets/upload` | Upload and validate a CSV |
| `GET` | `/api/datasets` | List uploaded datasets |
| `GET` | `/api/datasets/{id}` | Dataset detail + preview |
| `GET` | `/api/datasets/{id}/profile` | Column-level profiling |
| `GET` | `/api/datasets/{id}/quality` | Data quality report |
| `POST` | `/api/chat` | Ask a natural-language question |
| `POST` | `/api/anomalies` | Run anomaly detection |
| `POST` | `/api/forecast` | Run forecasting |
| `POST` | `/api/insights` | Generate business insights |
| `POST` | `/api/dashboard/generate` | Auto-generate KPIs + charts |
| `POST` | `/api/reports/export` | Export a Markdown report |
| `GET` | `/api/health` | Health check |

## Testing

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```
28 tests covering CSV upload/validation, data profiling, data quality
scoring, DuckDB SQL safety, anomaly detection, forecasting, agent intent
classification, end-to-end chat, and full API integration (via FastAPI's
`TestClient`) — all passing.

## Evaluation

See [`docs/evaluation.md`](docs/evaluation.md) — real, reproducible results
from running `backend/run_eval.py` against the actual sample datasets,
including two real bugs the evaluation caught and how they were fixed.

## Security

- **Read-only SQL only.** All DuckDB queries are validated to be `SELECT`/
  `WITH` statements; `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `ATTACH`,
  `PRAGMA`, and other dangerous keywords are blocked before execution.
- **No arbitrary code execution.** Pandas operations are expressed as a
  small structured schema with a whitelisted set of aggregation functions —
  never `eval`/`exec` of LLM- or user-authored code.
- **Upload validation.** File extension, size limits, encoding fallbacks,
  empty/malformed CSV detection, safe temp filenames (UUID-prefixed, no
  path traversal).
- **Server-side-only secrets.** LLM API keys are read from environment
  variables on the backend and never sent to or exposed in the frontend.
- **CORS** restricted to configured origins.
- **No stack traces to users.** All unhandled exceptions are caught and
  logged server-side with a generic, friendly message returned to the client.

## Design Decisions

- **Deterministic-first, LLM-optional.** Every numeric result is computed
  by Pandas/DuckDB/scikit-learn; the LLM (when configured) only polishes
  wording. This makes the app reliable, testable, cheap to run, and fully
  functional with zero API keys — a deliberate choice over a "wrap an LLM"
  approach.
- **Structured Pandas operations instead of code-gen + eval.** Rather than
  asking an LLM to write Python and executing it, analyses are represented
  as a small typed schema (filter/groupby/agg/sort/top-n) with a fixed,
  safe executor. This removes the injection surface entirely.
- **Rule-based intent classification with synonym dictionaries.** Business
  terms (revenue/sales/amount, region/area/territory, etc.) are matched
  against actual column names, so the app understands natural phrasing
  variations without needing an LLM call for every question.
- **ChromaDB is opt-in per dataset**, only for columns classified as free
  text (long, low-repetition strings) — never used for numeric analytics,
  per the assignment's explicit guidance.

## Limitations

- Semantic search requires one-time internet access to download the
  ChromaDB embedding model; disable via `SEMANTIC_SEARCH_ENABLED=false` for
  fully offline deployments (everything else still works).
- Forecasting uses a lightweight linear-trend + weekly-seasonality model —
  appropriate for a demo/assignment scope, not a production forecasting
  system for highly seasonal or multi-year data.
- Combined semantic + numeric queries need a shared column between the text
  dataset and the numeric dataset to group by; without one, the agent
  returns the semantic matches alone rather than guessing a join.
- Intent classification is rule-based by default; very unusual phrasing may
  be classified less accurately without an LLM key configured.

## Future Improvements

- True token-level streaming of the agent's staged progress (currently
  synchronous; the assignment explicitly discourages faking streaming with
  artificial delays, so this was left for a real SSE implementation)
- User authentication and per-user dataset isolation
- Persistent dataset storage across backend restarts (currently in-memory
  per process, with SQLite for conversation metadata only)
- PDF export in addition to Markdown reports
- More forecasting model options (e.g. Prophet-style decomposition) for
  strongly seasonal datasets

## Assumptions & Implementation Notes

- Currency formatting in generated explanations defaults to Indian numbering
  (₹, lakhs/crores) since the assignment originates from an India-based
  team; this is purely a display convenience in `agent._fmt()` and does not
  affect underlying calculations.
- "Top N" phrasing (e.g. "top 5", "5 best") is parsed via regex; unqualified
  superlatives ("highest", "most") default to N=1.
- When multiple datasets are uploaded and a question doesn't name one
  explicitly, the agent defaults to the single dataset (if only one is
  selected) or the most recently referenced one from conversation context.

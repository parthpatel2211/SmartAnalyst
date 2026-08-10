# SmartAnalyst — Rebuild Design

**Date:** 2026-08-10
**Status:** Approved
**Goal:** Turn SmartAnalyst from a demo-grade prototype into a portfolio-grade project that supports an application for **data analyst** roles.

---

## 1. Context

### What exists today

- FastAPI backend (`backend_app/`) with three modules; **only one is reachable**.
- Create React App frontend (`frontend_app/`) — a 400px chat bubble with WhatsApp-styled CSS.
- One 50-row synthetic CSV.
- A one-line README.

### Audit findings that drive this rebuild

| # | Finding | Severity |
|---|---|---|
| 1 | `exec()` of LLM-generated Python with `__import__` in the allowed builtins — the sandbox does not sandbox; `__import__('os').system(...)` executes | **Critical** |
| 2 | `profile_api.py` and `sql_query_api.py` routers are never registered — `/profile` and `/nl2sql` are dead code | **Critical** |
| 3 | `from smart_analyst import uploaded_df` binds `None` at import time — `/profile` could never work even if wired | High |
| 4 | No `requirements.txt` — backend is not installable | High |
| 5 | `sql_query.lower()` lowercases string literals, so `WHERE Region='North'` silently returns zero rows | High |
| 6 | SQL guard is `startswith("select")`, which `"select 1; drop table data"` defeats | High |
| 7 | Global mutable `uploaded_df` — all users share one dataset | High |
| 8 | `qa_history` is captured but never sent to the model, so follow-up questions do not work | Medium |
| 9 | API keys hardcoded as placeholders in source (verified: no real key in git history) | Medium |
| 10 | CRA (`react-scripts` 5, deprecated), hardcoded `127.0.0.1:8000`, `alert()` for feedback, no loading or error states | Medium |
| 11 | No tests, no CI, no Dockerfile, no LICENSE, no root `.gitignore` | Medium |
| 12 | `react-dropzone` and `recharts` installed but unused; CRA boilerplate left in place | Low |

### Non-goals

- Multi-user accounts, auth, or persistence beyond a session.
- Horizontal scaling. Single-worker is accepted and documented.
- Support for any LLM provider other than OpenAI.
- Any paid infrastructure.

---

## 2. Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Analysis engine | **DuckDB SQL + declarative chart spec** | Removes the arbitrary-code-execution attack surface entirely rather than containing it. Also makes generated SQL displayable, which is the single most relevant artifact for a data-analyst reviewer. |
| Frontend stack | Vite + React + TypeScript + Tailwind + Recharts | Replaces deprecated CRA. TypeScript kept deliberately light — typed API responses only, no advanced type machinery — so the code stays explainable in an interview. |
| API key handling | Bring-your-own-key | Public demo costs nothing to run and cannot be abused against the owner's account. |
| Backend host | Render free tier (Docker) | Simplest free Docker deploy. Cold start mitigated in the UI. |
| Frontend host | Vercel (static) | Free, instant, zero config for Vite. |
| Sample data | One generated ~5,000-row synthetic dataset | Fully controlled, no licensing questions, and can be constructed to exercise every analysis feature. |

### Explicitly cut from scope

- **Data quality score** — a weighted 0–100 is subjective and would need defending in an interview.
- **LLM-generated suggested questions** — replaced with static example questions bundled alongside the sample dataset. Zero LLM cost, and the empty state still feels alive for a first-time visitor.
- **Row-level anomaly detection** (z-score / isolation forest) — IQR outlier counts in the column profile cover the need at a fraction of the effort.

---

## 3. Architecture

```
Browser — Vercel (static)
  React + TypeScript + Tailwind + Recharts
  API key held in sessionStorage only; sent per-request as an X-OpenAI-Key header
        │  HTTPS
        ▼
FastAPI — Render (Docker, free tier)
  GET  /health                        warm-up ping
  POST /datasets                      CSV upload → session_id + schema + profile
  GET  /datasets/{id}/profile         full column profile
  GET  /datasets/{id}/insights        deterministic findings (no LLM)
  GET  /datasets/{id}/correlations    numeric correlation matrix
  POST /datasets/{id}/ask             NL question → SQL → rows + chart spec + summary
        │
        ▼
DuckDB, in-memory, one table named `data` per session
```

### Module layout

```
backend_app/
  main.py            app factory, CORS, router registration, exception handlers
  config.py          pydantic-settings; env-driven, no hardcoded values
  models.py          pydantic request/response schemas
  sessions.py        SessionStore: uuid → DatasetSession, TTL eviction, LRU cap
  profiling.py       column profile, correlations
  insights.py        deterministic finding generators
  sql_guard.py       sqlglot-based SQL validation  ← security boundary
  llm.py             OpenAI client wrapper, prompt construction, response parsing
  charts.py          chart-spec validation + shape-based fallback heuristic
  routers/
    datasets.py
    ask.py

frontend_app/src/
  api/client.ts      typed fetch wrapper, base URL from VITE_API_URL
  types.ts           API response types
  components/
    TopBar.tsx  Dropzone.tsx  SchemaPanel.tsx  ProfileAccordion.tsx
    InsightsPanel.tsx  CorrelationHeatmap.tsx
    Conversation.tsx  AnswerCard.tsx  ChartView.tsx  TableView.tsx  SqlView.tsx
    ApiKeyDialog.tsx  LoadingSteps.tsx  ErrorCard.tsx  EmptyState.tsx
  hooks/  lib/  App.tsx
```

Each module has one responsibility and a typed interface. `sql_guard.py` in particular is deliberately isolated so it can be tested exhaustively without any HTTP or LLM involvement.

**Migration approach:** both apps are rebuilt **in place**. `backend_app/`'s three existing files are replaced by the module layout above. `frontend_app/` is re-scaffolded on Vite, and all CRA artifacts are removed — `react-scripts`, `logo.svg`, `App.test.js`, `reportWebVitals.js`, `setupTests.js`, `public/manifest.json`, and the spinning-logo CSS. No parallel directory, no dead code left behind.

**Runtime and dependencies:** Python 3.11 pinned in the Dockerfile (3.13 is available locally but 3.11 has the widest wheel coverage for pandas/DuckDB on slim images). Backend dependencies declared in `requirements.txt` with pinned versions — `fastapi`, `uvicorn`, `pandas`, `duckdb`, `sqlglot`, `pydantic-settings`, `openai`, `python-multipart`, plus `pytest` and `ruff` in `requirements-dev.txt`. Node 22 for the frontend.

---

## 4. Session model

Replaces the module-level `uploaded_df` global.

```python
@dataclass
class DatasetSession:
    id: str                    # uuid4
    table_name: str            # always "data"
    df: pd.DataFrame
    conn: duckdb.DuckDBPyConnection
    schema: list[ColumnSchema]
    history: list[QATurn]      # last 3 turns, sent to the model as context
    created_at: datetime
    last_used_at: datetime
```

`SessionStore` is a process-local dict with:

- **TTL eviction** — 30 minutes since `last_used_at`, checked lazily on access.
- **LRU cap** — `MAX_SESSIONS` (default 25); oldest evicted when exceeded.
- **Upload limits** — 10 MB and 200,000 rows, enforced before parsing completes.

**Known limitation, documented in the README:** state is per-process, so the backend runs single-worker. Multi-worker would require an external store (Redis, or DuckDB files on shared disk). This is a deliberate trade-off for a free-tier demo, stated openly rather than hidden.

---

## 5. Security model

This is the section that justifies the entire architecture choice, and it gets a dedicated README subsection.

1. **No `exec`, no `eval`, anywhere in the codebase.** Enforced by a test that greps the source tree.
2. **SQL validated by AST, not string matching.** `sql_guard.validate(sql)` parses with `sqlglot` (DuckDB dialect) and rejects unless:
   - exactly one statement parses (defeats `select 1; drop table data`),
   - the root node is `Select` or `With`,
   - no node in the tree is DDL, DML, `Attach`, `Copy`, `Pragma`, `Install`, `Load`, or `Set`,
   - no comment-smuggled trailing statement survives normalization.
3. **DuckDB connection hardened** — `enable_external_access=false`, so no `read_csv('/etc/passwd')`, no HTTP reads, no filesystem escape from inside a query.
4. **Resource bounds** — `LIMIT 5000` injected when absent; per-query timeout; result payload size cap.
5. **Case preservation** — the query is never lowercased. This fixes finding #5; casing is handled by DuckDB's own identifier resolution.
6. **Key hygiene** — the user's OpenAI key is read from a request header, held only for the duration of the call, never logged, never persisted, never placed in a URL or query string. A logging filter redacts anything matching an API-key shape.
7. **Config from environment** — `.env.example` committed, `.env` gitignored, no secrets in source.

---

## 6. Analysis features

### 6.1 Column profile (`profiling.py`)

Per column:

- storage dtype, plus an **inferred semantic type**: `id | categorical | numeric | datetime | boolean | text`
- non-null count and null percentage
- distinct count and cardinality ratio
- top 5 values with frequencies
- numeric only: min, Q1, median, mean, Q3, max, std, skew, IQR-based outlier count

Dataset level: row count, column count, duplicate row count, memory footprint.

### 6.2 Auto-insights (`insights.py`) — deterministic, no LLM

Each generator is a pure function `(df, profile) -> list[Insight]`, where `Insight` carries a severity, a title, a one-line detail, and the columns involved:

- strongest correlations above a threshold
- columns exceeding a null-percentage threshold
- constant / single-value columns
- strongly skewed numeric distributions
- outlier-heavy columns (IQR count above a threshold)
- duplicate rows present
- high-cardinality categorical columns

Computed in pandas, instantly, at zero cost. This is the part that demonstrates statistical judgement rather than prompt engineering, so it is deliberately not delegated to the model.

### 6.3 Correlation matrix

Pearson over numeric columns, returned as a matrix plus a ranked pair list. Rendered as a heatmap.

### 6.4 Ask pipeline (`llm.py` + `charts.py`)

1. Build a prompt from: the question, the column schema with semantic types, 3 sample rows, and the last 3 Q&A turns (**fixes finding #8 — conversation memory is actually wired in**).
2. Model returns strict JSON: `{sql, chart, explanation}`.
3. `sql_guard.validate(sql)` — reject and surface the error if it fails.
4. Execute against DuckDB with timeout and row cap.
5. `charts.validate(chart, result_columns)` — if the proposed spec references columns the result does not have, fall back to the shape heuristic.
6. Return rows, the SQL, the chart spec, and the explanation.

**Chart spec:**

```ts
{ kind: "bar" | "line" | "area" | "scatter" | "histogram" | "table",
  x: string, y: string[], series?: string, title: string }
```

**Fallback heuristic** when the model's spec is invalid:

| Result shape | Chart |
|---|---|
| 1 datetime + ≥1 numeric | line |
| 1 categorical + 1 numeric, ≤ 25 rows | bar |
| 2 numerics | scatter |
| 1 numeric only | histogram |
| anything else | table |

Deliberately no pie charts — they encode quantity as angle, which is read less accurately than length, and a reviewer for a data role notices that choice.

---

## 7. Frontend

### Layout — analyst workspace

- **Top bar** — dataset name, row/column count, API-key status chip, theme toggle.
- **Left rail (collapsible)** — dropzone, schema table with type icons and null-percentage bars, "Load sample dataset", profile accordion.
- **Center** — conversation. Each answer is a card: one-line explanation, then tabs **`Chart | Table | SQL`**, plus export result CSV and export chart PNG.
- **Insights panel** — auto-findings list and correlation heatmap.

### States

- **Empty** — sample-dataset button plus static example-question chips.
- **Loading** — stepped indicator (*generating SQL → running query → rendering*) rather than a spinner, so the 3–5 second model call reads as deliberate progress.
- **Cold start** — `/health` pinged on mount; if the backend is asleep, show an explicit "waking the analysis server" state with a progress hint. Turns a free-tier constraint into a handled edge case.
- **Error** — inline card showing the failing SQL and the reason, with a retry action.
- **No key** — dialog explaining BYOK, with a clear statement that the key stays in the browser session and is never stored server-side.

### Design system

Charts and UI share one palette, verified for contrast in both light and dark themes. Tabular numerals for all figures. Consistent axis, legend, and tooltip treatment across every chart type.

---

## 8. Testing

**Backend (pytest):**

- `sql_guard` — the highest-value suite. Assert rejection of `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ATTACH`, `COPY`, `PRAGMA`, `INSTALL`, `LOAD`, multi-statement payloads, comment-smuggled statements, and CTEs wrapping a DML node. Assert acceptance of legitimate `SELECT` and `WITH` queries.
- `profiling` — correct stats on a fixture frame including nulls, a constant column, and a skewed column.
- `insights` — each generator fires on a frame built to trigger it and stays silent on one built not to.
- `charts` — fallback heuristic per result shape; invalid spec rejected.
- `sessions` — TTL eviction, LRU cap, upload limits.
- API routes with a mocked LLM.
- A source-tree test asserting no `exec(` or `eval(` appears in the backend.

**Frontend (Vitest + Testing Library):** API client error paths, chart-type selection, and the table/chart/SQL tab component.

**CI (GitHub Actions):** on push and PR — ruff + pytest for the backend, eslint + tsc + vitest + build for the frontend.

---

## 9. Repository deliverables

- **README** — banner, badges, live demo link, animated GIF, architecture diagram, feature list, quickstart (`docker compose up`), API reference table, a **Security** section explaining why no code execution happens, a **Known limitations** section, and a tech-stack list.
- `LICENSE` (MIT), root `.gitignore`, `.env.example`.
- `requirements.txt` and `Dockerfile` for the backend; `docker-compose.yml` for one-command local run.
- `scripts/generate_sample_data.py` producing the ~5,000-row synthetic dataset, committed alongside the CSV so the data is reproducible rather than mysterious.
- Delete the stale duplicate files at `D:\Projects\data_ai\` root (`smart_analyst.py`, `profile_api.py`, `sql_query_api.py`, `frontend/`, `sample_data.csv`). These sit outside the git repo, so this is local cleanup only — **confirm with the owner before deleting.**

### Sample dataset shape

~5,000 rows of synthetic e-commerce orders: `order_date`, `region`, `category`, `channel`, `units`, `unit_price`, `discount_pct`, `revenue`, `cost`, `profit`, `customer_segment`, `delivery_days`, `rating`. Constructed to contain a genuine `revenue`↔`cost` correlation, a deliberately skewed `revenue` distribution, injected nulls in `rating` and `delivery_days`, injected outliers in `units`, a small number of duplicate rows, and seasonality across `order_date` — so every profiling, insight, correlation, and chart-type path has something real to find.

---

## 10. Commit strategy

Conventional commits, small and scoped, so the log reads as deliberate engineering:

```
docs: add rebuild design spec
chore: add root gitignore, LICENSE, env example
feat(backend): session store replacing global dataframe state
feat(backend): sqlglot-based SQL validation
test(backend): SQL injection and guard test suite
feat(backend): column profiling and correlations
feat(backend): deterministic insight generators
feat(backend): NL-to-SQL ask pipeline with chart spec
feat(data): reproducible synthetic sample dataset
feat(frontend): scaffold Vite + TS + Tailwind, retire CRA
feat(frontend): dataset panel, schema, and profile views
feat(frontend): conversation with chart/table/SQL tabs
feat(frontend): insights panel and correlation heatmap
ci: lint, type-check, and test on push
docs: rewrite README
```

Nothing is pushed to `origin/master` without the owner reviewing the diff and approving it.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Model emits invalid or non-answering SQL | Guard rejects cleanly; error card shows the SQL and offers retry; explanation states what went wrong |
| Render cold start makes the demo look broken | `/health` warm-up ping plus an explicit "waking server" UI state |
| Rebuild scope creeps | Quality score, LLM suggestions, and anomaly detection already cut; ship the core three analysis features first |
| Losing free-form Python analysis | Accepted trade-off. SQL covers aggregation, filtering, grouping, joins, and window functions — which is what a data-analyst demo needs to show anyway |
| BYOK friction deters demo visitors | Sample dataset, profile, insights, and correlations all work with **no key at all**; a key is required only for natural-language questions |

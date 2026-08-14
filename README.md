# SmartAnalyst

**Ask questions about a CSV in plain English. Get an answer, the chart, and the SQL that produced it.**

[![CI](https://github.com/parthpatel2211/SmartAnalyst/actions/workflows/ci.yml/badge.svg)](https://github.com/parthpatel2211/SmartAnalyst/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

![SmartAnalyst workspace](docs/media/workspace-dark.png)

---

## What it does

Upload a CSV and SmartAnalyst profiles it immediately: column types, distributions, missing data, outliers, correlations, and a ranked list of what stands out. Then ask it questions in ordinary English and it answers them.

The distinguishing part is *how* it answers. SmartAnalyst translates each question into **DuckDB SQL**, validates that SQL against a read-only allowlist, runs it, and shows you the query alongside the answer. It never generates or executes Python.

**Profiling, insights, and correlations need no API key.** Only natural-language questions do, and you supply your own — the server never holds a credential.

---

## Why SQL instead of generated Python

The obvious way to build this is to have a language model write pandas code and `exec()` it. That is what the first version of this project did, and it is worth explaining why it no longer does, because the reasoning is the main engineering idea here.

Executing model-written code means running untrusted input as a program. The usual mitigation is a sandbox — a restricted `__builtins__`, a whitelist of allowed names. Sandboxes of that kind are very hard to make airtight; a single reachable import or dunder attribute reopens the whole machine.

Generating **SQL** instead changes the problem. A query is data, not a program: it is parsed into a syntax tree that can be inspected before anything executes, and it runs inside a database that has no concept of a filesystem. Rather than containing the risk, the risk stops existing.

It also produces a better tool. The generated SQL is shown to the user on every answer, which makes the result auditable instead of something you take on faith.

---

## Features

**Deterministic analysis** — computed in pandas, no model involved, so it is reproducible, instant, and free:

- Per-column profile: inferred semantic type (identifier, measure, category, date, boolean, text), null share, distinct counts, quartiles, standard deviation, skew, and IQR outlier counts
- Findings ranked by severity: strong correlations, missing data, constant columns, skewed distributions, outlier-heavy columns, duplicate rows, high cardinality
- Pearson correlation matrix, drawn as a diverging heatmap

**Natural-language questions** — question → validated SQL → result → a written answer:

- Answers are prose containing the actual numbers, written after the query runs
- Conversation memory, so follow-ups like *"now filter that to the West"* resolve
- Every answer carries **Answer / Chart / Table / SQL** tabs and a CSV export
- A chart opens by default only when the question asked to see one

**Bring your own key** — OpenAI (`sk-…`) and OpenRouter (`sk-or-…`) keys both work; the provider is chosen from the key. The key lives in your browser tab's session storage, is sent per request, and is never stored, logged, or written to disk.

---

## Architecture

```
Browser  ──  Vercel (static)
   React · TypeScript · Tailwind · Recharts
   Key held in sessionStorage, sent per request as X-OpenAI-Key
        │  HTTPS
        ▼
FastAPI  ──  Render (Docker)
   question ─► model ─► SQL ─► [ SQL GUARD ] ─► DuckDB ─► rows
                                    │
                          rejects anything not a
                          single read-only SELECT
        │
        ▼
   results ─► model ─► the written answer
```

Two model calls per question, and the reason is structural. The first writes SQL *before* anything has run, so at that point it has no result to report and can only restate its own intent — which is why a single-call version answers *"this query returns the total revenue for each region"* instead of naming the region. The second call sees the rows and writes the finding.

### API

| Method | Path | Purpose | Key required |
|---|---|---|---|
| `GET` | `/health` | Liveness, and cold-start detection | no |
| `POST` | `/datasets` | Upload a CSV, get a session and schema | no |
| `GET` | `/datasets/{id}/profile` | Full per-column statistics | no |
| `GET` | `/datasets/{id}/insights` | Ranked deterministic findings | no |
| `GET` | `/datasets/{id}/correlations` | Correlation matrix and ranked pairs | no |
| `POST` | `/datasets/{id}/ask` | Question → answer, SQL, rows, chart | **yes** |

---

## Security

The project's central claim is that model output is never executed as code. These are the controls that make it true, and the test suite enforces each one.

1. **No `exec`, `eval`, or `compile` anywhere in the backend.** A test greps the source tree and fails the build if any appears.
2. **SQL is validated by parsing, not by string matching.** `sqlglot` parses the query, which must be exactly one statement, rooted in a read-only node, containing no DDL, DML, `ATTACH`, `COPY`, `PRAGMA`, `INSTALL`, or `LOAD` node anywhere in its tree. Walking the whole tree matters: a CTE can wrap `DELETE … RETURNING` and still present a `SELECT` root.
3. **File-reading functions are denied by name** — `read_csv`, `read_parquet`, `glob`, the cross-database scanners. Checked against both the anonymous-function node and the typed nodes sqlglot promotes some functions to, because covering only one of those let `read_csv` through during development.
4. **DuckDB runs with external access disabled**, so a query that somehow evaded the guard still cannot reach the filesystem or the network.
5. **Queries are bounded** by an injected row limit and a timeout.
6. **The query is never case-folded.** An earlier version lowercased it, which rewrote string literals, so `WHERE region = 'North'` silently matched nothing.
7. **Keys are never persisted or logged.** They arrive in a header, live in a local variable for one call, and a logging filter redacts anything key-shaped as a backstop.

The SQL guard's test suite covers 27 rejection cases plus 12 evasion attempts retained after an adversarial pass — multi-statement payloads, comment-smuggled statements, DML hidden in CTEs, quoted and case-varied function names, and file readers reached through subqueries.

---

## Quickstart

```bash
git clone https://github.com/parthpatel2211/SmartAnalyst.git
cd SmartAnalyst
docker compose up
```

The API comes up on `http://localhost:8000`. For the frontend:

```bash
cd frontend_app
npm install
npm run dev
```

Open `http://localhost:5173` and click **Load sample dataset**. Everything except asking questions works without a key.

### Running it directly

```bash
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on Unix
pip install -r requirements-dev.txt
uvicorn backend_app.main:app --reload
```

Copy `.env.example` to `.env` to change any setting. No API key belongs in it — keys come from the caller, per request.

### Tests

```bash
pytest --cov=backend_app          # 226 tests
ruff check .
cd frontend_app && npm test       # 12 tests
```

### Regenerating the sample data

The bundled dataset is produced by a committed seeded script rather than shipped as an opaque file, so you can see exactly what was planted and confirm the tool finds it — a revenue-to-cost correlation, right-skewed prices, missing ratings, duplicate rows, seasonality, and bulk-order outliers carried by the wholesale channel.

```bash
python scripts/generate_sample_data.py
```

---

## Known limitations

Stated plainly, because they are real.

- **Single worker.** Session state is an in-process dictionary, so the API cannot be scaled horizontally as written. Multi-worker operation needs an external store. This is a deliberate trade-off for a free-tier deployment, not an oversight.
- **Sessions are ephemeral.** Uploads live in memory, expire after 30 minutes, and are capped in number. Nothing is written to disk, which is also the privacy story.
- **10 MB and 200,000 rows** per upload.
- **Only SQL-expressible questions.** Aggregation, filtering, grouping, ranking, and window functions are all available. Anything needing a regression or a custom statistical model is not.
- **Free-tier cold start.** The API sleeps when idle and can take up to a minute to wake. The frontend detects this and says so rather than appearing broken.
- **Answer quality depends on the model.** Smaller models occasionally propose a chart that does not fit the result; the server validates every chart against the columns actually returned and falls back to a shape heuristic rather than rendering something wrong.

---

## Tech stack

**Backend** — Python 3.11, FastAPI, DuckDB, sqlglot, pandas, pydantic-settings, pytest, ruff
**Frontend** — Vite, React 19, TypeScript, Tailwind CSS, Recharts, Vitest
**Infrastructure** — Docker, GitHub Actions, Render, Vercel

Charts follow a documented design method rather than library defaults: an eight-slot categorical palette assigned in fixed order and validated for colour-vision deficiency against both light and dark surfaces, a diverging scale for correlation so positive and negative read as opposites, and no pie charts — quantity encoded as angle is read less accurately than quantity encoded as length.

---

## License

MIT — see [LICENSE](LICENSE).

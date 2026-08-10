# SmartAnalyst Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild SmartAnalyst into a portfolio-grade natural-language data analysis tool that answers questions about an uploaded CSV by generating validated DuckDB SQL — never by executing generated Python.

**Architecture:** A FastAPI backend loads an uploaded CSV into a per-session in-memory DuckDB table. Questions go to OpenAI, which returns JSON containing SQL, a declarative chart spec, and an explanation. The SQL is validated by AST parse before execution; the chart spec is validated against actual result columns with a shape-based fallback. A Vite/React/TypeScript frontend renders results as interactive Recharts charts, sortable tables, and the generated SQL itself. Profiling, insights, and correlations are computed deterministically in pandas and require no API key.

**Tech Stack:** Python 3.11, FastAPI, DuckDB, sqlglot, pandas, pydantic-settings, OpenAI SDK, pytest, ruff · Node 22, Vite, React 19, TypeScript, Tailwind CSS, Recharts, Vitest, Testing Library · Docker, GitHub Actions, Render, Vercel

**Spec:** `docs/superpowers/specs/2026-08-10-smartanalyst-rebuild-design.md`

**Branch:** `feat/portfolio-rebuild` (already created; spec committed as `8f0a5fa`)

---

## Global Constraints

These apply to every task. A task's requirements implicitly include this section.

- **No `exec` or `eval` anywhere in the backend.** Task A12 adds a test that fails the build if either appears. This is the project's central claim; violating it invalidates the README.
- **No secrets in source.** All configuration through `pydantic-settings` reading environment variables. `.env` is gitignored; `.env.example` is committed with placeholder values.
- **The user's OpenAI key is never logged, never persisted to disk, never placed in a URL or query string.** It arrives in the `X-OpenAI-Key` request header, lives in a local variable for the duration of the call, and is discarded.
- **SQL is never lowercased, uppercased, or string-manipulated for validation.** Validation is AST-only. Case is DuckDB's problem.
- **Python 3.11** in the Dockerfile. Local development may use 3.13, but CI and the image pin 3.11.
- **Dependencies pinned** to exact versions in `requirements.txt` / `requirements-dev.txt`.
- **Every backend task is TDD:** write the failing test, run it and watch it fail, write the minimal implementation, run it and watch it pass, commit. Do not write implementation before a failing test exists.
- **Conventional commits**, one per task, scoped `feat(backend)`, `feat(frontend)`, `test(backend)`, `chore`, `ci`, `docs`.
- **Nothing is pushed to `origin`.** All work stays on the local `feat/portfolio-rebuild` branch until the owner reviews the full diff and approves the push.
- **Frontend API base URL** comes from `VITE_API_URL`, never hardcoded.
- **All charts avoid pie/donut.** Quantity is encoded as length or position, never angle.
- **Both light and dark themes** must be legible for every component and chart.

---

## File Structure

### Backend — `backend_app/`

| File | Responsibility |
|---|---|
| `main.py` | App factory, CORS, router registration, exception handlers, `/health` |
| `config.py` | `Settings` via pydantic-settings; all env-driven values |
| `models.py` | Pydantic request/response schemas shared across routers |
| `sessions.py` | `DatasetSession`, `SessionStore` — TTL eviction, LRU cap, upload limits |
| `sql_guard.py` | **Security boundary.** sqlglot AST validation. No HTTP, no LLM, no I/O |
| `engine.py` | DuckDB connection setup, hardening, query execution with limits |
| `profiling.py` | Column profile, semantic type inference, correlations |
| `insights.py` | Deterministic finding generators |
| `charts.py` | Chart-spec validation and shape-based fallback heuristic |
| `llm.py` | OpenAI client wrapper, prompt construction, strict JSON parsing |
| `logging_filters.py` | Redaction filter for anything resembling an API key |
| `routers/datasets.py` | `POST /datasets`, `GET /datasets/{id}/profile`, `/insights`, `/correlations` |
| `routers/ask.py` | `POST /datasets/{id}/ask` |

Deleted: the existing `smart_analyst.py`, `profile_api.py`, `sql_query_api.py`.

### Backend tests — `tests/`

`test_sql_guard.py` (largest), `test_engine.py`, `test_sessions.py`, `test_profiling.py`, `test_insights.py`, `test_charts.py`, `test_llm.py`, `test_routes_datasets.py`, `test_routes_ask.py`, `test_no_code_execution.py`, `conftest.py`.

### Frontend — `frontend_app/src/`

| File | Responsibility |
|---|---|
| `types.ts` | TypeScript mirrors of every API response |
| `api/client.ts` | Typed fetch wrapper, base URL, key header, error normalization |
| `lib/palette.ts` | Chart and UI color tokens for both themes |
| `lib/format.ts` | Number, percentage, and null formatting |
| `hooks/useApiKey.ts` | sessionStorage-backed key state |
| `hooks/useDataset.ts` | Upload, profile, insights, correlations fetching |
| `hooks/useConversation.ts` | Question submission, turn history, loading phases |
| `components/TopBar.tsx` | Dataset name, dimensions, key chip, theme toggle |
| `components/Dropzone.tsx` | File drop and sample-dataset load |
| `components/SchemaPanel.tsx` | Column list with type icons and null bars |
| `components/ProfileAccordion.tsx` | Per-column expanded statistics |
| `components/InsightsPanel.tsx` | Deterministic findings list |
| `components/CorrelationHeatmap.tsx` | Numeric correlation matrix |
| `components/Conversation.tsx` | Turn list and question input |
| `components/AnswerCard.tsx` | Explanation plus Chart/Table/SQL tabs and exports |
| `components/ChartView.tsx` | Recharts renderer driven by chart spec |
| `components/TableView.tsx` | Sortable, paginated result table |
| `components/SqlView.tsx` | Syntax-highlighted SQL with copy |
| `components/ApiKeyDialog.tsx` | BYOK entry and explanation |
| `components/LoadingSteps.tsx` | Stepped progress indicator |
| `components/ColdStartBanner.tsx` | Backend wake-up state |
| `components/ErrorCard.tsx` | Failure display with failing SQL and retry |
| `components/EmptyState.tsx` | Sample dataset and example-question chips |
| `App.tsx` | Layout composition and state wiring |

Deleted: `App.css`, `App.test.js`, `ChatInterface.js`, `ChatInterface.css`, `FileUploader.js`, `logo.svg`, `reportWebVitals.js`, `setupTests.js`, `public/manifest.json`, `public/logo192.png`, `public/logo512.png`.

### Root

`README.md`, `LICENSE`, `.gitignore`, `.env.example`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` (ruff + pytest config), `Dockerfile`, `docker-compose.yml`, `render.yaml`, `vercel.json`, `.github/workflows/ci.yml`, `scripts/generate_sample_data.py`, `data/sample_orders.csv`, `docs/architecture.svg`.

---

# Phase A — Backend

## Task A1: Project scaffolding, config, and health check

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, `.env.example`
- Create: `backend_app/__init__.py`, `backend_app/config.py`, `backend_app/main.py`, `backend_app/logging_filters.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_health.py`
- Delete: `backend_app/smart_analyst.py`, `backend_app/profile_api.py`, `backend_app/sql_query_api.py`

**Interfaces:**
- Consumes: nothing
- Produces: `create_app() -> FastAPI`; `Settings` with fields `openai_model: str`, `cors_origins: list[str]`, `max_upload_bytes: int`, `max_rows: int`, `session_ttl_seconds: int`, `max_sessions: int`, `query_timeout_seconds: int`, `default_row_limit: int`; `get_settings() -> Settings` (cached); `RedactingFilter` logging filter

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from backend_app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_have_no_hardcoded_secrets():
    from backend_app.config import get_settings
    settings = get_settings()
    assert not hasattr(settings, "openai_api_key"), (
        "The server must never hold an API key. Keys arrive per-request."
    )
```

```python
# tests/test_no_code_execution.py  (stub now, expanded in A12)
def test_placeholder_until_a12():
    assert True
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend_app.main'`

- [ ] **Step 3: Write `requirements.txt` and `requirements-dev.txt`**

```
# requirements.txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
pandas==2.2.3
duckdb==1.1.3
sqlglot==26.6.0
pydantic==2.10.5
pydantic-settings==2.7.1
openai==1.59.6
python-multipart==0.0.20
```

```
# requirements-dev.txt
-r requirements.txt
pytest==8.3.4
pytest-cov==6.0.0
httpx==0.28.1
ruff==0.9.2
```

- [ ] **Step 4: Write `config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Deliberately contains no API key.

    Keys are supplied per-request by the caller via the X-OpenAI-Key
    header, so the server never holds credentials of its own.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SMARTANALYST_")

    openai_model: str = "gpt-4o-mini"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_bytes: int = 10 * 1024 * 1024
    max_rows: int = 200_000
    session_ttl_seconds: int = 1800
    max_sessions: int = 25
    query_timeout_seconds: int = 15
    default_row_limit: int = 5000


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Write `logging_filters.py`**

```python
import logging
import re

_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")


class RedactingFilter(logging.Filter):
    """Strips anything shaped like an API key from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _KEY_PATTERN.sub("sk-***REDACTED***", record.msg)
        if record.args:
            record.args = tuple(
                _KEY_PATTERN.sub("sk-***REDACTED***", a) if isinstance(a, str) else a
                for a in record.args
            )
        return True
```

- [ ] **Step 6: Write `main.py`**

```python
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_app.config import get_settings
from backend_app.logging_filters import RedactingFilter


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger().addFilter(RedactingFilter())


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="SmartAnalyst API",
        description="Natural-language data analysis over CSV via validated DuckDB SQL.",
        version="2.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-OpenAI-Key"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 7: Write `pyproject.toml`, `.gitignore`, `.env.example`**

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "S"]
ignore = ["S101"]  # assert is fine in tests

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

```
# .gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.env
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
dist/
build/
.DS_Store
*.log
```

```
# .env.example
SMARTANALYST_OPENAI_MODEL=gpt-4o-mini
SMARTANALYST_CORS_ORIGINS=["http://localhost:5173"]
SMARTANALYST_MAX_UPLOAD_BYTES=10485760
SMARTANALYST_MAX_ROWS=200000
SMARTANALYST_SESSION_TTL_SECONDS=1800
```

- [ ] **Step 8: Delete the three legacy backend files**

```bash
git rm backend_app/smart_analyst.py backend_app/profile_api.py backend_app/sql_query_api.py
```

- [ ] **Step 9: Run the tests and verify they pass**

Run: `pytest tests/test_health.py -v && ruff check .`
Expected: 2 passed, ruff clean

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(backend): scaffold app factory, settings, and health check"
```

---

## Task A2: SQL guard — the security boundary

This is the most important task in the plan. The project's central claim is that no untrusted code executes; this module is what makes that true. Test it harder than anything else.

**Files:**
- Create: `backend_app/sql_guard.py`
- Test: `tests/test_sql_guard.py`

**Interfaces:**
- Consumes: nothing (deliberately dependency-free apart from sqlglot)
- Produces: `SqlValidationError(ValueError)`; `validate(sql: str, *, table: str = "data") -> str` returning normalized SQL or raising

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sql_guard.py
import pytest

from backend_app.sql_guard import SqlValidationError, validate

ALLOWED = [
    "SELECT * FROM data",
    "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
    "WITH t AS (SELECT * FROM data) SELECT COUNT(*) FROM t",
    "SELECT * FROM data WHERE region = 'North'",
    "SELECT a FROM data UNION ALL SELECT b FROM data",
    "SELECT region, RANK() OVER (ORDER BY SUM(revenue) DESC) FROM data GROUP BY region",
    "SELECT * FROM data ORDER BY revenue DESC LIMIT 10",
]

REJECTED = [
    # Direct mutation
    "DROP TABLE data",
    "DELETE FROM data",
    "UPDATE data SET revenue = 0",
    "INSERT INTO data VALUES (1)",
    "CREATE TABLE evil (x INT)",
    "ALTER TABLE data ADD COLUMN x INT",
    "TRUNCATE TABLE data",
    # Multi-statement smuggling — the bug in the original codebase
    "SELECT 1; DROP TABLE data",
    "SELECT 1;DROP TABLE data;",
    "SELECT 1; -- harmless\nDROP TABLE data",
    # Filesystem and extension escape
    "ATTACH 'evil.db' AS evil",
    "COPY data TO '/tmp/out.csv'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "PRAGMA database_list",
    "SET memory_limit = '100GB'",
    # File-reading functions, blocked independently of external-access config
    "SELECT * FROM read_csv_auto('/etc/passwd')",
    "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
    "SELECT * FROM glob('/**')",
    # DML hidden inside a CTE
    "WITH x AS (DELETE FROM data RETURNING *) SELECT * FROM x",
    # Garbage
    "",
    "   ",
    "not sql at all !!!",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allows_legitimate_read_queries(sql):
    assert validate(sql)


@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_dangerous_or_invalid_sql(sql):
    with pytest.raises(SqlValidationError):
        validate(sql)


def test_preserves_string_literal_case():
    """The original bug: lowercasing the query broke WHERE clauses."""
    out = validate("SELECT * FROM data WHERE region = 'North'")
    assert "'North'" in out
    assert "'north'" not in out


def test_error_message_is_actionable():
    with pytest.raises(SqlValidationError) as exc:
        validate("DROP TABLE data")
    assert "Drop" in str(exc.value) or "not permitted" in str(exc.value).lower()
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_sql_guard.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'backend_app.sql_guard'`

- [ ] **Step 3: Write `sql_guard.py`**

```python
"""AST-based validation for model-generated SQL.

The original implementation checked `sql.lower().startswith("select")`,
which `"select 1; drop table data"` walks straight past. This module
parses instead: exactly one statement, a read-only root node, and no
forbidden node or function anywhere in the tree.
"""

import sqlglot
from sqlglot import exp

DIALECT = "duckdb"

ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Except, exp.Intersect, exp.Subquery)

FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.TruncateTable, exp.Attach, exp.Detach, exp.Copy, exp.Pragma,
    exp.Set, exp.Use, exp.Grant, exp.Command,
)

# Blocked regardless of DuckDB's external-access setting: defence in depth.
FORBIDDEN_FUNCTIONS = frozenset({
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
    "read_text", "read_blob", "glob", "parquet_scan", "csv_scan", "iceberg_scan",
    "delta_scan", "postgres_scan", "sqlite_scan", "mysql_scan", "shell",
})


class SqlValidationError(ValueError):
    """Raised when generated SQL is not a single, read-only query."""


def validate(sql: str, *, table: str = "data") -> str:
    if not sql or not sql.strip():
        raise SqlValidationError("Empty query.")

    try:
        statements = [s for s in sqlglot.parse(sql, dialect=DIALECT) if s is not None]
    except Exception as err:
        raise SqlValidationError(f"Could not parse SQL: {err}") from err

    if len(statements) != 1:
        raise SqlValidationError(
            f"Expected exactly one statement, found {len(statements)}. "
            "Multiple statements are not permitted."
        )

    statement = statements[0]

    if not isinstance(statement, ALLOWED_ROOTS):
        raise SqlValidationError(
            f"{type(statement).__name__} is not permitted. Only read-only "
            "SELECT and WITH queries are allowed."
        )

    for node in statement.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlValidationError(
                f"{type(node).__name__} is not permitted anywhere in the query."
            )
        if isinstance(node, exp.Anonymous):
            name = (node.name or "").lower()
            if name in FORBIDDEN_FUNCTIONS:
                raise SqlValidationError(f"Function {name}() is not permitted.")

    return statement.sql(dialect=DIALECT)
```

Note on `walk()`: sqlglot yields the root itself first, so the root-type check and the walk overlap harmlessly. If the installed sqlglot version yields `(node, parent, key)` tuples instead of bare nodes, unpack accordingly — verify against the pinned `26.6.0` behaviour when the test runs.

- [ ] **Step 4: Run and verify pass**

Run: `pytest tests/test_sql_guard.py -v`
Expected: all parametrized cases pass. If any `REJECTED` case passes validation, **stop and fix the guard** — do not adjust the test to match the implementation.

- [ ] **Step 5: Commit**

```bash
git add backend_app/sql_guard.py tests/test_sql_guard.py
git commit -m "feat(backend): AST-based SQL validation replacing string prefix check"
```

---

## Task A3: DuckDB engine with hardened connection

**Files:**
- Create: `backend_app/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `sql_guard.validate`
- Produces: `create_connection(df: pd.DataFrame, table: str = "data") -> duckdb.DuckDBPyConnection`; `run_query(conn, sql: str, *, row_limit: int) -> QueryResult`; `QueryResult` dataclass with `columns: list[str]`, `rows: list[dict]`, `row_count: int`, `truncated: bool`, `sql: str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine.py
import pandas as pd
import pytest

from backend_app.engine import create_connection, run_query
from backend_app.sql_guard import SqlValidationError


@pytest.fixture
def conn():
    df = pd.DataFrame({"region": ["North", "South", "North"], "revenue": [10, 20, 30]})
    return create_connection(df)


def test_runs_a_grouped_query(conn):
    result = run_query(conn, "SELECT region, SUM(revenue) AS total FROM data GROUP BY region", row_limit=100)
    assert result.row_count == 2
    assert set(result.columns) == {"region", "total"}
    totals = {r["region"]: r["total"] for r in result.rows}
    assert totals == {"North": 40, "South": 20}


def test_case_sensitive_string_filter_still_matches(conn):
    """Regression: the old code lowercased the query, so 'North' became 'north'."""
    result = run_query(conn, "SELECT * FROM data WHERE region = 'North'", row_limit=100)
    assert result.row_count == 2


def test_dangerous_sql_is_rejected_before_execution(conn):
    with pytest.raises(SqlValidationError):
        run_query(conn, "DROP TABLE data", row_limit=100)
    assert run_query(conn, "SELECT COUNT(*) AS n FROM data", row_limit=10).rows[0]["n"] == 3


def test_row_limit_truncates_and_flags(conn):
    result = run_query(conn, "SELECT * FROM data", row_limit=2)
    assert result.row_count == 2
    assert result.truncated is True


def test_external_file_access_is_disabled(conn):
    with pytest.raises(Exception):
        conn.execute("SELECT * FROM read_csv_auto('/etc/passwd')")


def test_nan_becomes_none_for_json(conn):
    df = pd.DataFrame({"x": [1.0, None]})
    c = create_connection(df)
    result = run_query(c, "SELECT * FROM data ORDER BY x NULLS LAST", row_limit=10)
    assert result.rows[1]["x"] is None
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_engine.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Write `engine.py`**

```python
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from backend_app.sql_guard import validate


@dataclass(frozen=True)
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool


def create_connection(df: pd.DataFrame, table: str = "data") -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with filesystem and network access disabled."""
    conn = duckdb.connect(database=":memory:")
    conn.execute("SET enable_external_access = false")
    conn.register("_incoming", df)
    conn.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _incoming')
    conn.unregister("_incoming")
    return conn


def run_query(conn: duckdb.DuckDBPyConnection, sql: str, *, row_limit: int) -> QueryResult:
    safe_sql = validate(sql)
    # Fetch one extra row to detect truncation without a second COUNT query.
    frame = conn.execute(
        f"SELECT * FROM ({safe_sql}) AS _q LIMIT {int(row_limit) + 1}"
    ).fetch_df()

    truncated = len(frame) > row_limit
    if truncated:
        frame = frame.head(row_limit)

    frame = frame.replace({np.nan: None})
    return QueryResult(
        sql=safe_sql,
        columns=list(frame.columns),
        rows=frame.to_dict(orient="records"),
        row_count=len(frame),
        truncated=truncated,
    )
```

If wrapping in a subquery breaks a legitimate top-level `ORDER BY ... LIMIT`, adjust to append `LIMIT` only when the parsed statement has no existing limit, using `sqlglot` to inspect. Verify with the `test_row_limit_truncates_and_flags` case.

- [ ] **Step 4: Run and verify pass**

Run: `pytest tests/test_engine.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend_app/engine.py tests/test_engine.py
git commit -m "feat(backend): hardened DuckDB engine with validated query execution"
```

---

## Task A4: Session store replacing global dataframe state

**Files:**
- Create: `backend_app/sessions.py`, `backend_app/models.py`
- Test: `tests/test_sessions.py`

**Interfaces:**
- Consumes: `engine.create_connection`, `config.get_settings`
- Produces: `DatasetSession` dataclass (`id`, `name`, `df`, `conn`, `schema`, `history`, `created_at`, `last_used_at`); `SessionStore` with `create(df, name) -> DatasetSession`, `get(session_id) -> DatasetSession` (raises `SessionNotFound`), `evict_expired()`, `__len__`; `SessionNotFound(KeyError)`; `UploadTooLarge(ValueError)`; `read_csv_limited(raw: bytes, *, max_bytes: int, max_rows: int) -> pd.DataFrame`
- Produces in `models.py`: `ColumnSchema`, `ColumnProfile`, `DatasetProfile`, `Insight`, `ChartSpec`, `AskRequest`, `AskResponse`, `UploadResponse` (Pydantic models; exact fields defined in the tasks that populate them)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sessions.py
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from backend_app.sessions import (
    SessionNotFound, SessionStore, UploadTooLarge, read_csv_limited,
)

DF = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


def test_create_and_get_roundtrip():
    store = SessionStore(ttl_seconds=1800, max_sessions=5)
    session = store.create(DF, name="test.csv")
    assert store.get(session.id) is session
    assert session.schema[0].name == "a"


def test_unknown_session_raises():
    store = SessionStore(ttl_seconds=1800, max_sessions=5)
    with pytest.raises(SessionNotFound):
        store.get("nope")


def test_expired_session_is_evicted():
    store = SessionStore(ttl_seconds=60, max_sessions=5)
    session = store.create(DF, name="t.csv")
    session.last_used_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    with pytest.raises(SessionNotFound):
        store.get(session.id)


def test_lru_cap_evicts_oldest():
    store = SessionStore(ttl_seconds=1800, max_sessions=2)
    first = store.create(DF, name="1.csv")
    store.create(DF, name="2.csv")
    store.create(DF, name="3.csv")
    assert len(store) == 2
    with pytest.raises(SessionNotFound):
        store.get(first.id)


def test_get_refreshes_last_used():
    store = SessionStore(ttl_seconds=1800, max_sessions=5)
    session = store.create(DF, name="t.csv")
    before = session.last_used_at
    store.get(session.id)
    assert session.last_used_at >= before


def test_rejects_oversized_upload():
    with pytest.raises(UploadTooLarge):
        read_csv_limited(b"a,b\n1,2\n" * 100, max_bytes=10, max_rows=1000)


def test_rejects_too_many_rows():
    raw = ("a\n" + "1\n" * 50).encode()
    with pytest.raises(UploadTooLarge):
        read_csv_limited(raw, max_bytes=10_000, max_rows=10)


def test_history_keeps_only_last_three_turns():
    store = SessionStore(ttl_seconds=1800, max_sessions=5)
    session = store.create(DF, name="t.csv")
    for i in range(5):
        session.add_turn(question=f"q{i}", sql=f"SELECT {i}", summary=f"s{i}")
    assert len(session.history) == 3
    assert session.history[0].question == "q2"
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_sessions.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Write `models.py` (schema types needed now)**

```python
from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    semantic_type: str  # id | categorical | numeric | datetime | boolean | text
    null_pct: float
    distinct_count: int


class QATurn(BaseModel):
    question: str
    sql: str
    summary: str
```

- [ ] **Step 4: Write `sessions.py`**

```python
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd

from backend_app.engine import create_connection
from backend_app.models import ColumnSchema, QATurn
from backend_app.profiling import build_schema

MAX_HISTORY_TURNS = 3


class SessionNotFound(KeyError):
    """Requested session does not exist or has expired."""


class UploadTooLarge(ValueError):
    """Upload exceeded the configured byte or row limit."""


def read_csv_limited(raw: bytes, *, max_bytes: int, max_rows: int) -> pd.DataFrame:
    if len(raw) > max_bytes:
        raise UploadTooLarge(
            f"File is {len(raw) / 1_048_576:.1f} MB; the limit is "
            f"{max_bytes / 1_048_576:.0f} MB."
        )
    # Read one row past the limit so we can tell "at limit" from "over limit".
    frame = pd.read_csv(io.BytesIO(raw), nrows=max_rows + 1)
    if len(frame) > max_rows:
        raise UploadTooLarge(f"File has more than {max_rows:,} rows.")
    if frame.empty or not len(frame.columns):
        raise UploadTooLarge("File contains no data.")
    return frame


@dataclass
class DatasetSession:
    id: str
    name: str
    df: pd.DataFrame
    conn: duckdb.DuckDBPyConnection
    schema: list[ColumnSchema]
    created_at: datetime
    last_used_at: datetime
    history: list[QATurn] = field(default_factory=list)

    def add_turn(self, *, question: str, sql: str, summary: str) -> None:
        self.history.append(QATurn(question=question, sql=sql, summary=summary))
        del self.history[:-MAX_HISTORY_TURNS]

    def touch(self) -> None:
        self.last_used_at = datetime.now(timezone.utc)


class SessionStore:
    """Process-local session storage.

    Deliberately in-memory: this is a single-worker free-tier deployment.
    Multi-worker operation would require an external store; that trade-off
    is documented in the README rather than hidden.
    """

    def __init__(self, *, ttl_seconds: int, max_sessions: int) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max = max_sessions
        self._sessions: dict[str, DatasetSession] = {}

    def __len__(self) -> int:
        return len(self._sessions)

    def create(self, df: pd.DataFrame, *, name: str) -> DatasetSession:
        self.evict_expired()
        now = datetime.now(timezone.utc)
        session = DatasetSession(
            id=str(uuid.uuid4()),
            name=name,
            df=df,
            conn=create_connection(df),
            schema=build_schema(df),
            created_at=now,
            last_used_at=now,
        )
        self._sessions[session.id] = session
        self._enforce_cap()
        return session

    def get(self, session_id: str) -> DatasetSession:
        self.evict_expired()
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(
                "That dataset session has expired or does not exist. Upload the file again."
            )
        session.touch()
        return session

    def evict_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - self._ttl
        for sid in [s.id for s in self._sessions.values() if s.last_used_at < cutoff]:
            self._close(sid)

    def _enforce_cap(self) -> None:
        while len(self._sessions) > self._max:
            oldest = min(self._sessions.values(), key=lambda s: s.last_used_at)
            self._close(oldest.id)

    def _close(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.conn.close()
```

Note: `create` calls `build_schema` from Task A5. Write A5 first if executing strictly in dependency order, or stub `build_schema` returning `[]` and let A5's tests drive the real implementation.

- [ ] **Step 5: Run and verify pass**

Run: `pytest tests/test_sessions.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add backend_app/sessions.py backend_app/models.py tests/test_sessions.py
git commit -m "feat(backend): session store replacing global dataframe state"
```

---

## Task A5: Column profiling and semantic type inference

**Files:**
- Create: `backend_app/profiling.py`
- Modify: `backend_app/models.py` (add `ColumnProfile`, `DatasetProfile`, `CorrelationMatrix`)
- Test: `tests/test_profiling.py`

**Interfaces:**
- Consumes: `models.ColumnSchema`
- Produces: `build_schema(df) -> list[ColumnSchema]`; `infer_semantic_type(series) -> str`; `profile_dataset(df) -> DatasetProfile`; `correlations(df) -> CorrelationMatrix`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profiling.py
import numpy as np
import pandas as pd
import pytest

from backend_app.profiling import (
    build_schema, correlations, infer_semantic_type, profile_dataset,
)


@pytest.fixture
def frame():
    rng = np.random.default_rng(42)
    n = 200
    revenue = rng.gamma(shape=2.0, scale=100.0, size=n)  # right-skewed
    return pd.DataFrame({
        "order_id": range(1, n + 1),
        "order_date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "region": rng.choice(["North", "South", "East", "West"], n),
        "revenue": revenue,
        "cost": revenue * 0.6 + rng.normal(0, 5, n),  # strongly correlated
        "is_returned": rng.choice([True, False], n),
        "rating": np.where(rng.random(n) < 0.3, np.nan, rng.integers(1, 6, n)),
        "constant": ["same"] * n,
    })


def test_infers_semantic_types(frame):
    types = {c.name: c.semantic_type for c in build_schema(frame)}
    assert types["order_id"] == "id"
    assert types["order_date"] == "datetime"
    assert types["region"] == "categorical"
    assert types["revenue"] == "numeric"
    assert types["is_returned"] == "boolean"


def test_profile_reports_dataset_shape(frame):
    profile = profile_dataset(frame)
    assert profile.row_count == 200
    assert profile.column_count == 8
    assert profile.duplicate_rows == 0


def test_numeric_column_has_full_statistics(frame):
    profile = profile_dataset(frame)
    revenue = next(c for c in profile.columns if c.name == "revenue")
    assert revenue.min is not None and revenue.max is not None
    assert revenue.q1 < revenue.median < revenue.q3
    assert revenue.skew > 0.5, "gamma-distributed revenue should be right-skewed"
    assert revenue.outlier_count >= 0


def test_null_percentage_is_reported(frame):
    profile = profile_dataset(frame)
    rating = next(c for c in profile.columns if c.name == "rating")
    assert 20 < rating.null_pct < 40


def test_top_values_are_ranked(frame):
    profile = profile_dataset(frame)
    region = next(c for c in profile.columns if c.name == "region")
    assert len(region.top_values) <= 5
    counts = [v.count for v in region.top_values]
    assert counts == sorted(counts, reverse=True)


def test_constant_column_has_one_distinct_value(frame):
    profile = profile_dataset(frame)
    constant = next(c for c in profile.columns if c.name == "constant")
    assert constant.distinct_count == 1


def test_correlations_find_the_planted_relationship(frame):
    matrix = correlations(frame)
    pair = next(
        p for p in matrix.pairs
        if {p.x, p.y} == {"revenue", "cost"}
    )
    assert pair.value > 0.9


def test_correlations_ignore_non_numeric_columns(frame):
    matrix = correlations(frame)
    assert "region" not in matrix.columns


def test_empty_numeric_set_returns_empty_matrix():
    matrix = correlations(pd.DataFrame({"a": ["x", "y"]}))
    assert matrix.columns == []
    assert matrix.pairs == []
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_profiling.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Add the profile models to `models.py`**

```python
class TopValue(BaseModel):
    value: str
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic_type: str
    non_null_count: int
    null_pct: float
    distinct_count: int
    cardinality_ratio: float
    top_values: list[TopValue] = []
    # Numeric only; None for other types.
    min: float | None = None
    q1: float | None = None
    median: float | None = None
    mean: float | None = None
    q3: float | None = None
    max: float | None = None
    std: float | None = None
    skew: float | None = None
    outlier_count: int | None = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    memory_bytes: int
    columns: list[ColumnProfile]


class CorrelationPair(BaseModel):
    x: str
    y: str
    value: float


class CorrelationMatrix(BaseModel):
    columns: list[str]
    matrix: list[list[float | None]]
    pairs: list[CorrelationPair]  # ranked by absolute value, descending
```

- [ ] **Step 4: Write `profiling.py`**

```python
import numpy as np
import pandas as pd

from backend_app.models import (
    ColumnProfile, ColumnSchema, CorrelationMatrix, CorrelationPair,
    DatasetProfile, TopValue,
)

ID_CARDINALITY_THRESHOLD = 0.95
CATEGORICAL_MAX_DISTINCT = 50


def infer_semantic_type(series: pd.Series) -> str:
    """Classify a column beyond its storage dtype.

    Storage dtype says 'int64'; an analyst wants to know whether that is an
    identifier or a measure, because the two get charted very differently.
    """
    non_null = series.dropna()
    if non_null.empty:
        return "text"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        ratio = non_null.nunique() / len(non_null)
        looks_like_key = (
            ratio >= ID_CARDINALITY_THRESHOLD
            and pd.api.types.is_integer_dtype(series)
        )
        return "id" if looks_like_key else "numeric"
    if non_null.nunique() <= CATEGORICAL_MAX_DISTINCT:
        return "categorical"
    return "text"


def build_schema(df: pd.DataFrame) -> list[ColumnSchema]:
    total = max(len(df), 1)
    return [
        ColumnSchema(
            name=str(col),
            dtype=str(df[col].dtype),
            semantic_type=infer_semantic_type(df[col]),
            null_pct=round(float(df[col].isna().sum()) / total * 100, 2),
            distinct_count=int(df[col].nunique(dropna=True)),
        )
        for col in df.columns
    ]


def _numeric_stats(series: pd.Series) -> dict:
    values = series.dropna().astype(float)
    if values.empty:
        return {}
    q1, median, q3 = (float(values.quantile(q)) for q in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    outliers = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
    return {
        "min": float(values.min()),
        "q1": q1,
        "median": median,
        "mean": float(values.mean()),
        "q3": q3,
        "max": float(values.max()),
        "std": float(values.std()) if len(values) > 1 else 0.0,
        "skew": float(values.skew()) if len(values) > 2 else 0.0,
        "outlier_count": outliers,
    }


def _top_values(series: pd.Series, limit: int = 5) -> list[TopValue]:
    counts = series.dropna().value_counts().head(limit)
    return [TopValue(value=str(idx), count=int(n)) for idx, n in counts.items()]


def profile_dataset(df: pd.DataFrame) -> DatasetProfile:
    total = max(len(df), 1)
    columns = []
    for col in df.columns:
        series = df[col]
        semantic = infer_semantic_type(series)
        non_null = int(series.notna().sum())
        distinct = int(series.nunique(dropna=True))
        stats = _numeric_stats(series) if semantic in {"numeric", "id"} else {}
        columns.append(ColumnProfile(
            name=str(col),
            dtype=str(series.dtype),
            semantic_type=semantic,
            non_null_count=non_null,
            null_pct=round((len(df) - non_null) / total * 100, 2),
            distinct_count=distinct,
            cardinality_ratio=round(distinct / total, 4),
            top_values=_top_values(series) if semantic in {"categorical", "boolean", "text"} else [],
            **stats,
        ))

    return DatasetProfile(
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_rows=int(df.duplicated().sum()),
        memory_bytes=int(df.memory_usage(deep=True).sum()),
        columns=columns,
    )


def correlations(df: pd.DataFrame) -> CorrelationMatrix:
    numeric = df.select_dtypes(include=[np.number])
    # An identifier column correlates with row order, not with anything meaningful.
    numeric = numeric[[c for c in numeric.columns if infer_semantic_type(df[c]) == "numeric"]]

    if numeric.shape[1] < 2:
        return CorrelationMatrix(columns=[], matrix=[], pairs=[])

    corr = numeric.corr(method="pearson")
    names = [str(c) for c in corr.columns]
    matrix = [[None if pd.isna(v) else round(float(v), 4) for v in row] for row in corr.to_numpy()]

    pairs = [
        CorrelationPair(x=names[i], y=names[j], value=round(float(corr.iat[i, j]), 4))
        for i in range(len(names))
        for j in range(i + 1, len(names))
        if not pd.isna(corr.iat[i, j])
    ]
    pairs.sort(key=lambda p: abs(p.value), reverse=True)
    return CorrelationMatrix(columns=names, matrix=matrix, pairs=pairs)
```

- [ ] **Step 5: Run and verify pass**

Run: `pytest tests/test_profiling.py tests/test_sessions.py -v`
Expected: all pass (A4's session tests now work with the real `build_schema`)

- [ ] **Step 6: Commit**

```bash
git add backend_app/profiling.py backend_app/models.py tests/test_profiling.py
git commit -m "feat(backend): column profiling, semantic types, and correlations"
```

---

## Task A6: Deterministic insight generators

**Files:**
- Create: `backend_app/insights.py`
- Modify: `backend_app/models.py` (add `Insight`)
- Test: `tests/test_insights.py`

**Interfaces:**
- Consumes: `profiling.profile_dataset`, `profiling.correlations`, `models.DatasetProfile`
- Produces: `generate_insights(df, profile, corr) -> list[Insight]`; individual generators `_strong_correlations`, `_high_null_columns`, `_constant_columns`, `_skewed_columns`, `_outlier_heavy_columns`, `_duplicate_rows`, `_high_cardinality_columns`

Each generator is a pure function returning `list[Insight]`. This is the module that demonstrates statistical judgement rather than prompt engineering, which is why it uses no LLM.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_insights.py
import numpy as np
import pandas as pd

from backend_app.insights import generate_insights
from backend_app.profiling import correlations, profile_dataset


def _insights_for(df):
    return generate_insights(df, profile_dataset(df), correlations(df))


def _kinds(insights):
    return {i.kind for i in insights}


def test_detects_strong_correlation():
    x = np.arange(100, dtype=float)
    df = pd.DataFrame({"x": x, "y": x * 2 + 1})
    assert "strong_correlation" in _kinds(_insights_for(df))


def test_ignores_weak_correlation():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=200), "y": rng.normal(size=200)})
    assert "strong_correlation" not in _kinds(_insights_for(df))


def test_detects_high_null_column():
    df = pd.DataFrame({"a": [1] * 100, "b": [None] * 70 + [1] * 30})
    insights = _insights_for(df)
    assert "high_nulls" in _kinds(insights)
    assert any("b" in i.columns for i in insights if i.kind == "high_nulls")


def test_detects_constant_column():
    df = pd.DataFrame({"a": range(50), "flag": ["yes"] * 50})
    assert "constant_column" in _kinds(_insights_for(df))


def test_detects_skewed_distribution():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"v": rng.gamma(1.2, 50.0, 500), "w": rng.normal(0, 1, 500)})
    insights = [i for i in _insights_for(df) if i.kind == "skewed"]
    assert any("v" in i.columns for i in insights)


def test_detects_duplicate_rows():
    df = pd.concat([pd.DataFrame({"a": [1, 2, 3]})] * 2, ignore_index=True)
    assert "duplicate_rows" in _kinds(_insights_for(df))


def test_detects_outlier_heavy_column():
    values = list(np.zeros(100)) + [1000.0] * 12
    df = pd.DataFrame({"v": values})
    assert "outliers" in _kinds(_insights_for(df))


def test_clean_dataset_produces_no_warnings():
    rng = np.random.default_rng(2)
    df = pd.DataFrame({
        "a": rng.normal(0, 1, 300),
        "b": rng.normal(5, 2, 300),
        "c": rng.choice(["x", "y", "z"], 300),
    })
    kinds = _kinds(_insights_for(df))
    assert "high_nulls" not in kinds
    assert "constant_column" not in kinds
    assert "duplicate_rows" not in kinds


def test_insights_are_sorted_by_severity():
    df = pd.DataFrame({"a": [None] * 90 + [1] * 10, "b": ["k"] * 100})
    severities = [i.severity for i in _insights_for(df)]
    order = {"high": 0, "medium": 1, "low": 2}
    assert severities == sorted(severities, key=lambda s: order[s])
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_insights.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Add the `Insight` model**

```python
class Insight(BaseModel):
    kind: str       # strong_correlation | high_nulls | constant_column | skewed |
                    # outliers | duplicate_rows | high_cardinality
    severity: str   # high | medium | low
    title: str
    detail: str
    columns: list[str] = []
```

- [ ] **Step 4: Write `insights.py`**

```python
import pandas as pd

from backend_app.models import CorrelationMatrix, DatasetProfile, Insight

CORRELATION_THRESHOLD = 0.7
HIGH_NULL_PCT = 20.0
CRITICAL_NULL_PCT = 50.0
SKEW_THRESHOLD = 1.0
OUTLIER_PCT_THRESHOLD = 5.0
HIGH_CARDINALITY_RATIO = 0.5

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _strong_correlations(corr: CorrelationMatrix) -> list[Insight]:
    out = []
    for pair in corr.pairs[:3]:
        if abs(pair.value) < CORRELATION_THRESHOLD:
            break
        direction = "positively" if pair.value > 0 else "negatively"
        out.append(Insight(
            kind="strong_correlation",
            severity="medium",
            title=f"{pair.x} and {pair.y} are strongly {direction} correlated",
            detail=f"Pearson r = {pair.value:.2f}. One may be derivable from the other.",
            columns=[pair.x, pair.y],
        ))
    return out


def _high_null_columns(profile: DatasetProfile) -> list[Insight]:
    out = []
    for col in profile.columns:
        if col.null_pct >= HIGH_NULL_PCT:
            critical = col.null_pct >= CRITICAL_NULL_PCT
            out.append(Insight(
                kind="high_nulls",
                severity="high" if critical else "medium",
                title=f"{col.name} is {col.null_pct:.0f}% missing",
                detail=(
                    "More than half the values are absent; aggregates over this "
                    "column will be unreliable."
                    if critical else
                    "Consider whether missing values should be imputed or excluded."
                ),
                columns=[col.name],
            ))
    return out


def _constant_columns(profile: DatasetProfile) -> list[Insight]:
    return [
        Insight(
            kind="constant_column",
            severity="low",
            title=f"{col.name} has a single value throughout",
            detail="A constant column carries no information and can be dropped.",
            columns=[col.name],
        )
        for col in profile.columns
        if col.distinct_count <= 1 and profile.row_count > 1
    ]


def _skewed_columns(profile: DatasetProfile) -> list[Insight]:
    out = []
    for col in profile.columns:
        if col.semantic_type != "numeric" or col.skew is None:
            continue
        if abs(col.skew) >= SKEW_THRESHOLD:
            side = "right" if col.skew > 0 else "left"
            out.append(Insight(
                kind="skewed",
                severity="low",
                title=f"{col.name} is {side}-skewed",
                detail=(
                    f"Skew = {col.skew:.2f}, so the mean ({col.mean:.2f}) is pulled "
                    f"away from the median ({col.median:.2f}). Prefer the median."
                ),
                columns=[col.name],
            ))
    return out


def _outlier_heavy_columns(profile: DatasetProfile) -> list[Insight]:
    out = []
    for col in profile.columns:
        if col.outlier_count is None or col.non_null_count == 0:
            continue
        pct = col.outlier_count / col.non_null_count * 100
        if pct >= OUTLIER_PCT_THRESHOLD:
            out.append(Insight(
                kind="outliers",
                severity="medium",
                title=f"{col.name} has {col.outlier_count} outliers ({pct:.0f}%)",
                detail="Values beyond 1.5×IQR from the quartiles. Check for data-entry errors.",
                columns=[col.name],
            ))
    return out


def _duplicate_rows(profile: DatasetProfile) -> list[Insight]:
    if profile.duplicate_rows == 0:
        return []
    pct = profile.duplicate_rows / max(profile.row_count, 1) * 100
    return [Insight(
        kind="duplicate_rows",
        severity="high" if pct >= 5 else "medium",
        title=f"{profile.duplicate_rows} duplicate rows ({pct:.1f}%)",
        detail="Identical rows will double-count in any aggregation.",
    )]


def _high_cardinality_columns(profile: DatasetProfile) -> list[Insight]:
    return [
        Insight(
            kind="high_cardinality",
            severity="low",
            title=f"{col.name} has {col.distinct_count} distinct values",
            detail="Too many categories to chart directly; group or filter before plotting.",
            columns=[col.name],
        )
        for col in profile.columns
        if col.semantic_type in {"categorical", "text"}
        and col.cardinality_ratio >= HIGH_CARDINALITY_RATIO
        and col.distinct_count > 20
    ]


def generate_insights(
    df: pd.DataFrame, profile: DatasetProfile, corr: CorrelationMatrix
) -> list[Insight]:
    insights = [
        *_duplicate_rows(profile),
        *_high_null_columns(profile),
        *_strong_correlations(corr),
        *_outlier_heavy_columns(profile),
        *_skewed_columns(profile),
        *_constant_columns(profile),
        *_high_cardinality_columns(profile),
    ]
    insights.sort(key=lambda i: _SEVERITY_ORDER[i.severity])
    return insights
```

- [ ] **Step 5: Run and verify pass**

Run: `pytest tests/test_insights.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add backend_app/insights.py backend_app/models.py tests/test_insights.py
git commit -m "feat(backend): deterministic insight generators"
```

---

## Task A7: Chart spec validation and fallback heuristic

**Files:**
- Create: `backend_app/charts.py`
- Modify: `backend_app/models.py` (add `ChartSpec`)
- Test: `tests/test_charts.py`

**Interfaces:**
- Consumes: `engine.QueryResult`, `profiling.infer_semantic_type`
- Produces: `resolve_chart(proposed: dict | None, result: QueryResult) -> ChartSpec`; `fallback_chart(result: QueryResult) -> ChartSpec`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charts.py
import pandas as pd

from backend_app.charts import resolve_chart
from backend_app.engine import QueryResult


def _result(df: pd.DataFrame) -> QueryResult:
    return QueryResult(
        sql="SELECT 1", columns=list(df.columns),
        rows=df.to_dict(orient="records"), row_count=len(df), truncated=False,
    )


def test_accepts_a_valid_proposed_spec():
    result = _result(pd.DataFrame({"region": ["N", "S"], "total": [1, 2]}))
    spec = resolve_chart({"kind": "bar", "x": "region", "y": ["total"], "title": "T"}, result)
    assert spec.kind == "bar"
    assert spec.title == "T"


def test_rejects_spec_referencing_a_missing_column():
    result = _result(pd.DataFrame({"region": ["N"], "total": [1]}))
    spec = resolve_chart({"kind": "bar", "x": "nope", "y": ["total"], "title": "T"}, result)
    assert spec.x == "region", "should fall back rather than emit a broken chart"


def test_rejects_unknown_chart_kind():
    result = _result(pd.DataFrame({"region": ["N"], "total": [1]}))
    spec = resolve_chart({"kind": "pie", "x": "region", "y": ["total"], "title": "T"}, result)
    assert spec.kind == "bar", "pie is never produced"


def test_fallback_datetime_and_numeric_gives_line():
    df = pd.DataFrame({"d": pd.date_range("2024-01-01", periods=5), "v": range(5)})
    assert resolve_chart(None, _result(df)).kind == "line"


def test_fallback_categorical_and_numeric_gives_bar():
    df = pd.DataFrame({"c": ["a", "b", "c"], "v": [1, 2, 3]})
    assert resolve_chart(None, _result(df)).kind == "bar"


def test_fallback_two_numerics_gives_scatter():
    df = pd.DataFrame({"x": [1.5, 2.5, 3.5], "y": [4.5, 5.5, 6.5]})
    assert resolve_chart(None, _result(df)).kind == "scatter"


def test_fallback_single_numeric_gives_histogram():
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0]})
    assert resolve_chart(None, _result(df)).kind == "histogram"


def test_fallback_many_categories_gives_table():
    df = pd.DataFrame({"c": [f"cat{i}" for i in range(60)], "v": range(60)})
    assert resolve_chart(None, _result(df)).kind == "table"


def test_single_scalar_result_gives_table():
    assert resolve_chart(None, _result(pd.DataFrame({"n": [42]}))).kind == "table"


def test_empty_result_gives_table():
    assert resolve_chart(None, _result(pd.DataFrame({"a": []}))).kind == "table"
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_charts.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Add the `ChartSpec` model**

```python
from typing import Literal

ChartKind = Literal["bar", "line", "area", "scatter", "histogram", "table"]


class ChartSpec(BaseModel):
    kind: ChartKind
    x: str | None = None
    y: list[str] = []
    series: str | None = None
    title: str = ""
```

- [ ] **Step 4: Write `charts.py`**

```python
"""Chart selection.

The model proposes a spec; we verify it against the columns the query
actually returned. A confidently wrong chart is worse than a table, so
anything unverifiable falls back to a shape-based heuristic.

No pie or donut charts are produced. Quantity encoded as angle is read
less accurately than quantity encoded as length or position.
"""

import pandas as pd

from backend_app.engine import QueryResult
from backend_app.models import ChartSpec
from backend_app.profiling import infer_semantic_type

VALID_KINDS = {"bar", "line", "area", "scatter", "histogram", "table"}
MAX_BAR_CATEGORIES = 25


def _frame(result: QueryResult) -> pd.DataFrame:
    return pd.DataFrame(result.rows, columns=result.columns)


def _classify(result: QueryResult) -> dict[str, list[str]]:
    frame = _frame(result)
    buckets: dict[str, list[str]] = {
        "numeric": [], "datetime": [], "categorical": [], "other": []
    }
    for col in result.columns:
        series = pd.to_numeric(frame[col], errors="ignore") if not frame.empty else frame[col]
        semantic = infer_semantic_type(series) if not frame.empty else "text"
        if semantic in {"numeric", "id"}:
            buckets["numeric"].append(col)
        elif semantic == "datetime":
            buckets["datetime"].append(col)
        elif semantic in {"categorical", "boolean"}:
            buckets["categorical"].append(col)
        else:
            buckets["other"].append(col)
    return buckets


def fallback_chart(result: QueryResult) -> ChartSpec:
    if result.row_count == 0 or not result.columns:
        return ChartSpec(kind="table", title="Result")

    b = _classify(result)
    numeric, datetime_cols, categorical = b["numeric"], b["datetime"], b["categorical"]

    if datetime_cols and numeric:
        return ChartSpec(kind="line", x=datetime_cols[0], y=numeric[:3], title="Trend over time")

    if categorical and numeric and result.row_count <= MAX_BAR_CATEGORIES:
        return ChartSpec(kind="bar", x=categorical[0], y=numeric[:3], title="Comparison by category")

    if len(numeric) >= 2 and not categorical:
        return ChartSpec(kind="scatter", x=numeric[0], y=[numeric[1]], title="Relationship")

    if len(numeric) == 1 and not categorical and result.row_count > 1:
        return ChartSpec(kind="histogram", x=numeric[0], y=[], title="Distribution")

    return ChartSpec(kind="table", title="Result")


def resolve_chart(proposed: dict | None, result: QueryResult) -> ChartSpec:
    if not proposed:
        return fallback_chart(result)

    kind = str(proposed.get("kind", "")).lower()
    if kind not in VALID_KINDS:
        return fallback_chart(result)
    if kind == "table":
        return ChartSpec(kind="table", title=str(proposed.get("title") or "Result"))

    available = set(result.columns)
    x = proposed.get("x")
    y = proposed.get("y") or []
    if isinstance(y, str):
        y = [y]

    if x is not None and x not in available:
        return fallback_chart(result)
    if any(col not in available for col in y):
        return fallback_chart(result)
    if kind != "histogram" and not y:
        return fallback_chart(result)

    series = proposed.get("series")
    if series is not None and series not in available:
        series = None

    return ChartSpec(
        kind=kind, x=x, y=list(y), series=series,
        title=str(proposed.get("title") or "Result"),
    )
```

- [ ] **Step 5: Run and verify pass**

Run: `pytest tests/test_charts.py -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add backend_app/charts.py backend_app/models.py tests/test_charts.py
git commit -m "feat(backend): chart spec validation with shape-based fallback"
```

---

## Task A8: LLM module — prompt construction and strict JSON parsing

**Files:**
- Create: `backend_app/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `models.ColumnSchema`, `models.QATurn`
- Produces: `build_prompt(question, schema, sample_rows, history) -> list[dict]`; `LlmResponse` dataclass (`sql: str`, `chart: dict | None`, `explanation: str`); `parse_response(raw: str) -> LlmResponse`; `ask_model(api_key, model, messages) -> str`; `LlmError(RuntimeError)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
import pytest

from backend_app.llm import LlmError, build_prompt, parse_response
from backend_app.models import ColumnSchema, QATurn

SCHEMA = [
    ColumnSchema(name="region", dtype="object", semantic_type="categorical",
                 null_pct=0.0, distinct_count=4),
    ColumnSchema(name="revenue", dtype="float64", semantic_type="numeric",
                 null_pct=0.0, distinct_count=500),
]


def test_prompt_includes_schema_and_semantic_types():
    messages = build_prompt("total revenue by region", SCHEMA, [{"region": "N", "revenue": 1.0}], [])
    text = " ".join(m["content"] for m in messages)
    assert "region" in text and "revenue" in text
    assert "categorical" in text and "numeric" in text


def test_prompt_includes_conversation_history():
    """Regression: the original code collected history but never sent it."""
    history = [QATurn(question="revenue by region", sql="SELECT 1", summary="Totals per region.")]
    text = " ".join(m["content"] for m in build_prompt("now only the West", SCHEMA, [], history))
    assert "revenue by region" in text


def test_prompt_forbids_non_select():
    text = " ".join(m["content"] for m in build_prompt("q", SCHEMA, [], []))
    assert "SELECT" in text
    assert "single" in text.lower()


def test_parses_clean_json():
    parsed = parse_response(
        '{"sql": "SELECT 1", "chart": {"kind": "bar"}, "explanation": "Ran it."}'
    )
    assert parsed.sql == "SELECT 1"
    assert parsed.chart == {"kind": "bar"}
    assert parsed.explanation == "Ran it."


def test_parses_json_wrapped_in_a_fenced_code_block():
    parsed = parse_response('```json\n{"sql": "SELECT 1", "explanation": "x"}\n```')
    assert parsed.sql == "SELECT 1"
    assert parsed.chart is None


def test_missing_sql_raises():
    with pytest.raises(LlmError):
        parse_response('{"explanation": "no query here"}')


def test_unparseable_output_raises():
    with pytest.raises(LlmError):
        parse_response("I'm sorry, I can't help with that.")
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL, module not found

- [ ] **Step 3: Write `llm.py`**

```python
import json
import re
from dataclasses import dataclass

from openai import OpenAI

from backend_app.models import ColumnSchema, QATurn

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

SYSTEM_PROMPT = """You are a senior data analyst. You answer questions about a \
single DuckDB table named `data` by writing SQL.

Rules:
- Return a single SELECT (or WITH ... SELECT) statement. Never more than one \
statement. Never DDL, DML, ATTACH, COPY, PRAGMA, INSTALL, or LOAD.
- Never call file-reading functions such as read_csv or read_parquet.
- Preserve the exact case of string literals; the data is case-sensitive.
- Prefer explicit column aliases so results are readable.
- Choose a chart that suits the result shape. Never choose a pie chart.

Respond with JSON only, matching exactly this shape:
{"sql": "<the query>",
 "chart": {"kind": "bar|line|area|scatter|histogram|table",
           "x": "<column>", "y": ["<column>"], "series": null,
           "title": "<short title>"},
 "explanation": "<one sentence describing what the query returns>"}"""


class LlmError(RuntimeError):
    """The model returned something unusable."""


@dataclass(frozen=True)
class LlmResponse:
    sql: str
    chart: dict | None
    explanation: str


def build_prompt(
    question: str,
    schema: list[ColumnSchema],
    sample_rows: list[dict],
    history: list[QATurn],
) -> list[dict]:
    schema_lines = "\n".join(
        f"- {c.name} ({c.dtype}, {c.semantic_type}, "
        f"{c.distinct_count} distinct, {c.null_pct:.0f}% null)"
        for c in schema
    )

    parts = [f"Table `data` columns:\n{schema_lines}"]
    if sample_rows:
        parts.append(f"Sample rows:\n{json.dumps(sample_rows[:3], default=str)}")
    if history:
        prior = "\n".join(
            f"Q: {t.question}\nSQL: {t.sql}\nResult: {t.summary}" for t in history
        )
        parts.append(
            f"Earlier in this conversation:\n{prior}\n"
            "Resolve any references like 'that' or 'those' against the above."
        )
    parts.append(f"Question: {question}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def parse_response(raw: str) -> LlmResponse:
    cleaned = _FENCE.sub("", (raw or "").strip()).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise LlmError(
            "The model did not return valid JSON. Try rephrasing the question."
        ) from err

    if not isinstance(payload, dict) or not payload.get("sql"):
        raise LlmError("The model did not return a SQL query for that question.")

    chart = payload.get("chart")
    return LlmResponse(
        sql=str(payload["sql"]).strip(),
        chart=chart if isinstance(chart, dict) else None,
        explanation=str(payload.get("explanation", "")).strip(),
    )


def ask_model(api_key: str, model: str, messages: list[dict]) -> str:
    """Single OpenAI call. The key is used here and never stored or logged."""
    client = OpenAI(api_key=api_key, timeout=30.0)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as err:
        raise LlmError(f"The language model call failed: {type(err).__name__}") from err
    return completion.choices[0].message.content or ""
```

The `except Exception` deliberately reports only the exception type, never its message — provider errors sometimes echo the request, and the request carries the key.

- [ ] **Step 4: Run and verify pass**

Run: `pytest tests/test_llm.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend_app/llm.py tests/test_llm.py
git commit -m "feat(backend): LLM prompt construction with conversation memory"
```

---

## Task A9: Dataset routes

**Files:**
- Create: `backend_app/routers/__init__.py`, `backend_app/routers/datasets.py`, `backend_app/deps.py`
- Modify: `backend_app/main.py` (register routers — **this is the fix for the dead-router bug**)
- Modify: `backend_app/models.py` (add `UploadResponse`)
- Test: `tests/test_routes_datasets.py`

**Interfaces:**
- Consumes: `sessions.SessionStore`, `profiling`, `insights`, `config`
- Produces: `get_store() -> SessionStore` (module-level singleton in `deps.py`); routes `POST /datasets`, `GET /datasets/{id}/profile`, `GET /datasets/{id}/insights`, `GET /datasets/{id}/correlations`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_routes_datasets.py
import io

import pytest
from fastapi.testclient import TestClient

from backend_app.main import create_app

CSV = b"region,revenue,cost\nNorth,100,60\nSouth,200,120\nNorth,150,90\n"


@pytest.fixture
def client():
    return TestClient(create_app())


def _upload(client, data=CSV, filename="t.csv"):
    return client.post("/datasets", files={"file": (filename, io.BytesIO(data), "text/csv")})


def test_upload_returns_session_and_schema(client):
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["session_id"]
    assert body["row_count"] == 3
    assert {c["name"] for c in body["schema"]} == {"region", "revenue", "cost"}


def test_registered_routes_exist(client):
    """Regression: /profile and /nl2sql were never registered in the original app."""
    paths = {r.path for r in create_app().routes}
    assert "/datasets" in paths
    assert "/datasets/{session_id}/profile" in paths
    assert "/datasets/{session_id}/insights" in paths
    assert "/datasets/{session_id}/correlations" in paths
    assert "/datasets/{session_id}/ask" in paths


def test_profile_returns_real_statistics(client):
    """Regression: the original /profile imported the dataframe by value at
    import time, so it was permanently None."""
    sid = _upload(client).json()["session_id"]
    body = client.get(f"/datasets/{sid}/profile").json()
    assert body["row_count"] == 3
    revenue = next(c for c in body["columns"] if c["name"] == "revenue")
    assert revenue["median"] == 150


def test_insights_endpoint_returns_a_list(client):
    sid = _upload(client).json()["session_id"]
    response = client.get(f"/datasets/{sid}/insights")
    assert response.status_code == 200
    assert isinstance(response.json()["insights"], list)


def test_correlations_endpoint(client):
    sid = _upload(client).json()["session_id"]
    body = client.get(f"/datasets/{sid}/correlations").json()
    assert set(body["columns"]) == {"revenue", "cost"}


def test_unknown_session_returns_404(client):
    assert client.get("/datasets/does-not-exist/profile").status_code == 404


def test_non_csv_upload_returns_400(client):
    response = client.post(
        "/datasets", files={"file": ("x.txt", io.BytesIO(b"not,a\ncsv"), "text/plain")}
    )
    assert response.status_code == 400


def test_analysis_endpoints_need_no_api_key(client):
    """Profiling must work with no key so a first-time visitor sees real output."""
    sid = _upload(client).json()["session_id"]
    for path in ("profile", "insights", "correlations"):
        assert client.get(f"/datasets/{sid}/{path}").status_code == 200
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_routes_datasets.py -v`
Expected: FAIL on every case except possibly the 404

- [ ] **Step 3: Write `deps.py`**

```python
from functools import lru_cache

from backend_app.config import get_settings
from backend_app.sessions import SessionStore


@lru_cache
def get_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(
        ttl_seconds=settings.session_ttl_seconds,
        max_sessions=settings.max_sessions,
    )
```

- [ ] **Step 4: Add `UploadResponse` to `models.py`**

```python
class UploadResponse(BaseModel):
    session_id: str
    name: str
    row_count: int
    column_count: int
    schema: list[ColumnSchema]
```

- [ ] **Step 5: Write `routers/datasets.py`**

```python
from fastapi import APIRouter, HTTPException, UploadFile

from backend_app.config import get_settings
from backend_app.deps import get_store
from backend_app.insights import generate_insights
from backend_app.models import (
    CorrelationMatrix, DatasetProfile, UploadResponse,
)
from backend_app.profiling import correlations, profile_dataset
from backend_app.sessions import SessionNotFound, UploadTooLarge, read_csv_limited

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _session_or_404(session_id: str):
    try:
        return get_store().get(session_id)
    except SessionNotFound as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("", status_code=201, response_model=UploadResponse)
async def upload_dataset(file: UploadFile) -> UploadResponse:
    settings = get_settings()
    raw = await file.read()
    try:
        frame = read_csv_limited(
            raw, max_bytes=settings.max_upload_bytes, max_rows=settings.max_rows
        )
    except UploadTooLarge as err:
        raise HTTPException(status_code=413, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=400, detail=f"Could not read that file as CSV: {err}"
        ) from err

    session = get_store().create(frame, name=file.filename or "dataset.csv")
    return UploadResponse(
        session_id=session.id,
        name=session.name,
        row_count=len(frame),
        column_count=len(frame.columns),
        schema=session.schema,
    )


@router.get("/{session_id}/profile", response_model=DatasetProfile)
async def get_profile(session_id: str) -> DatasetProfile:
    return profile_dataset(_session_or_404(session_id).df)


@router.get("/{session_id}/insights")
async def get_insights(session_id: str) -> dict:
    df = _session_or_404(session_id).df
    profile = profile_dataset(df)
    return {"insights": generate_insights(df, profile, correlations(df))}


@router.get("/{session_id}/correlations", response_model=CorrelationMatrix)
async def get_correlations(session_id: str) -> CorrelationMatrix:
    return correlations(_session_or_404(session_id).df)
```

- [ ] **Step 6: Register the routers in `main.py`**

Add inside `create_app()`, after the CORS middleware:

```python
    from backend_app.routers import ask, datasets

    app.include_router(datasets.router)
    app.include_router(ask.router)
```

This single change is what makes the dead endpoints reachable. Task A10 creates `ask.py`; if running A9 alone, create `backend_app/routers/ask.py` with an empty `router = APIRouter()` so the import resolves, and A10 fills it in.

- [ ] **Step 7: Run and verify pass**

Run: `pytest tests/test_routes_datasets.py -v`
Expected: 8 passed

- [ ] **Step 8: Commit**

```bash
git add backend_app/routers backend_app/deps.py backend_app/main.py backend_app/models.py tests/test_routes_datasets.py
git commit -m "feat(backend): dataset upload, profile, insights, and correlation routes"
```

---

## Task A10: Ask route — the full pipeline

**Files:**
- Create: `backend_app/routers/ask.py`
- Modify: `backend_app/models.py` (add `AskRequest`, `AskResponse`)
- Test: `tests/test_routes_ask.py`

**Interfaces:**
- Consumes: `llm`, `sql_guard`, `engine`, `charts`, `sessions`, `deps.get_store`
- Produces: route `POST /datasets/{session_id}/ask` accepting `AskRequest` and the `X-OpenAI-Key` header, returning `AskResponse`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_routes_ask.py
import io
import json

import pytest
from fastapi.testclient import TestClient

from backend_app.main import create_app

CSV = b"region,revenue\nNorth,100\nSouth,200\nNorth,150\n"
KEY = {"X-OpenAI-Key": "sk-test-key-not-real-000000000000"}


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def session_id(client):
    response = client.post("/datasets", files={"file": ("t.csv", io.BytesIO(CSV), "text/csv")})
    return response.json()["session_id"]


def _mock_model(monkeypatch, payload: dict):
    monkeypatch.setattr(
        "backend_app.routers.ask.ask_model",
        lambda api_key, model, messages: json.dumps(payload),
    )


def test_happy_path_returns_rows_sql_and_chart(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {
        "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
        "chart": {"kind": "bar", "x": "region", "y": ["total"], "title": "Revenue by region"},
        "explanation": "Total revenue per region.",
    })
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "revenue by region"}, headers=KEY
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chart"]["kind"] == "bar"
    assert body["row_count"] == 2
    assert "GROUP BY" in body["sql"].upper()
    assert body["explanation"]


def test_missing_api_key_returns_401(client, session_id):
    response = client.post(f"/datasets/{session_id}/ask", json={"question": "anything"})
    assert response.status_code == 401


def test_dangerous_generated_sql_is_blocked(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {
        "sql": "SELECT 1; DROP TABLE data", "chart": None, "explanation": "oops",
    })
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "delete everything"}, headers=KEY
    )
    assert response.status_code == 400
    assert "statement" in response.json()["detail"].lower()


def test_data_survives_a_blocked_query(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {"sql": "DROP TABLE data", "chart": None, "explanation": ""})
    client.post(f"/datasets/{session_id}/ask", json={"question": "drop"}, headers=KEY)
    _mock_model(monkeypatch, {
        "sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "count",
    })
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "count"}, headers=KEY
    ).json()
    assert body["rows"][0]["n"] == 3


def test_invalid_chart_spec_falls_back_instead_of_failing(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {
        "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
        "chart": {"kind": "bar", "x": "nonexistent", "y": ["total"], "title": "T"},
        "explanation": "x",
    })
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    ).json()
    assert body["chart"]["x"] == "region"


def test_conversation_history_is_recorded(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {
        "sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "counted",
    })
    for _ in range(2):
        client.post(f"/datasets/{session_id}/ask", json={"question": "count"}, headers=KEY)

    captured = {}

    def capture(api_key, model, messages):
        captured["text"] = " ".join(m["content"] for m in messages)
        return json.dumps({"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})

    monkeypatch.setattr("backend_app.routers.ask.ask_model", capture)
    client.post(f"/datasets/{session_id}/ask", json={"question": "again"}, headers=KEY)
    assert "counted" in captured["text"], "prior turns must reach the model"


def test_unknown_session_returns_404(client):
    response = client.post("/datasets/nope/ask", json={"question": "q"}, headers=KEY)
    assert response.status_code == 404


def test_api_key_is_not_echoed_in_any_response(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    )
    assert KEY["X-OpenAI-Key"] not in response.text
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_routes_ask.py -v`
Expected: FAIL

- [ ] **Step 3: Add `AskRequest` / `AskResponse` to `models.py`**

```python
class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    sql: str
    explanation: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    chart: ChartSpec
```

- [ ] **Step 4: Write `routers/ask.py`**

```python
import logging

from fastapi import APIRouter, Header, HTTPException

from backend_app.charts import resolve_chart
from backend_app.config import get_settings
from backend_app.deps import get_store
from backend_app.engine import run_query
from backend_app.llm import LlmError, ask_model, build_prompt, parse_response
from backend_app.models import AskRequest, AskResponse
from backend_app.sessions import SessionNotFound
from backend_app.sql_guard import SqlValidationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["ask"])


@router.post("/{session_id}/ask", response_model=AskResponse)
async def ask(
    session_id: str,
    payload: AskRequest,
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
) -> AskResponse:
    if not x_openai_key:
        raise HTTPException(
            status_code=401,
            detail="An OpenAI API key is required to ask questions. "
                   "Profiling and insights work without one.",
        )

    try:
        session = get_store().get(session_id)
    except SessionNotFound as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    settings = get_settings()
    sample = session.df.head(3).to_dict(orient="records")
    messages = build_prompt(payload.question, session.schema, sample, session.history)

    try:
        raw = ask_model(x_openai_key, settings.openai_model, messages)
        proposal = parse_response(raw)
    except LlmError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    logger.info("Generated SQL for session %s: %s", session_id, proposal.sql)

    try:
        result = run_query(session.conn, proposal.sql, row_limit=settings.default_row_limit)
    except SqlValidationError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=400,
            detail=f"The generated query failed to run: {err}",
        ) from err

    chart = resolve_chart(proposal.chart, result)
    session.add_turn(
        question=payload.question,
        sql=result.sql,
        summary=proposal.explanation or f"{result.row_count} rows returned.",
    )

    return AskResponse(
        question=payload.question,
        sql=result.sql,
        explanation=proposal.explanation,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        chart=chart,
    )
```

- [ ] **Step 5: Run and verify pass**

Run: `pytest -v`
Expected: entire suite green

- [ ] **Step 6: Commit**

```bash
git add backend_app/routers/ask.py backend_app/models.py tests/test_routes_ask.py
git commit -m "feat(backend): ask pipeline wiring LLM, SQL guard, engine, and charts"
```

---

## Task A11: Reproducible synthetic sample dataset

**Files:**
- Create: `scripts/generate_sample_data.py`, `data/sample_orders.csv`, `data/example_questions.json`
- Delete: `data/sample_data.csv`
- Test: `tests/test_sample_data.py`

**Interfaces:**
- Produces: a ~5,000-row CSV containing every condition the analysis features detect

The dataset is generated by a committed, seeded script rather than being an opaque blob. A reviewer can see exactly what was planted and verify the tool finds it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sample_data.py
import pandas as pd
import pytest

from backend_app.insights import generate_insights
from backend_app.profiling import correlations, profile_dataset

CSV = "data/sample_orders.csv"


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(CSV, parse_dates=["order_date"])


def test_has_enough_rows(df):
    assert len(df) >= 5000


def test_exercises_every_insight_kind(df):
    profile = profile_dataset(df)
    kinds = {i.kind for i in generate_insights(df, profile, correlations(df))}
    for expected in {"strong_correlation", "high_nulls", "outliers", "duplicate_rows", "skewed"}:
        assert expected in kinds, f"sample data should trigger {expected}"


def test_has_every_semantic_type(df):
    types = {c.semantic_type for c in profile_dataset(df).columns}
    assert {"numeric", "categorical", "datetime"} <= types


def test_generator_is_deterministic():
    from scripts.generate_sample_data import build
    assert build().equals(build())
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_sample_data.py -v`
Expected: FAIL, file not found

- [ ] **Step 3: Write `scripts/generate_sample_data.py`**

```python
"""Generate the bundled demo dataset.

Every condition the analysis features detect is planted deliberately and
documented here, so the demo demonstrably finds real things rather than
happening to look busy.

Planted: a revenue-cost correlation, right-skewed revenue, nulls in rating
and delivery_days, outliers in units, exact duplicate rows, and seasonality
in order_date.
"""

import numpy as np
import pandas as pd

SEED = 20260810
N = 5000


def build() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)

    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(
        rng.integers(0, 730, N), unit="D"
    )
    month = dates.month
    seasonality = 1.0 + 0.35 * np.sin((month - 1) / 12 * 2 * np.pi)

    category = rng.choice(["Apparel", "Footwear", "Accessories", "Outerwear"], N,
                          p=[0.35, 0.28, 0.22, 0.15])
    region = rng.choice(["North", "South", "East", "West"], N)
    channel = rng.choice(["Online", "Retail", "Wholesale"], N, p=[0.55, 0.32, 0.13])
    segment = rng.choice(["Consumer", "Corporate", "Home Office"], N, p=[0.6, 0.25, 0.15])

    units = rng.integers(1, 12, N).astype(float)
    # Planted outliers: 1% of orders are bulk purchases.
    outlier_idx = rng.choice(N, size=N // 100, replace=False)
    units[outlier_idx] = rng.integers(400, 900, len(outlier_idx))

    unit_price = np.round(rng.gamma(3.0, 18.0, N) + 5, 2)  # right-skewed
    discount = np.round(rng.choice([0, 0.05, 0.1, 0.15, 0.25], N,
                                   p=[0.5, 0.2, 0.15, 0.1, 0.05]), 2)
    revenue = np.round(units * unit_price * (1 - discount) * seasonality, 2)
    # Planted correlation: cost tracks revenue with noise.
    cost = np.round(revenue * rng.normal(0.62, 0.04, N).clip(0.4, 0.85), 2)
    profit = np.round(revenue - cost, 2)

    delivery_days = rng.integers(1, 15, N).astype(float)
    rating = rng.integers(1, 6, N).astype(float)
    # Planted nulls.
    rating[rng.random(N) < 0.18] = np.nan
    delivery_days[rng.random(N) < 0.07] = np.nan

    frame = pd.DataFrame({
        "order_id": np.arange(1, N + 1),
        "order_date": dates,
        "region": region,
        "category": category,
        "channel": channel,
        "customer_segment": segment,
        "units": units.astype(int),
        "unit_price": unit_price,
        "discount_pct": discount,
        "revenue": revenue,
        "cost": cost,
        "profit": profit,
        "delivery_days": delivery_days,
        "rating": rating,
    }).sort_values("order_date").reset_index(drop=True)

    # Planted duplicates: 40 exact repeats, as real exports often contain.
    dupes = frame.sample(40, random_state=SEED)
    return pd.concat([frame, dupes], ignore_index=True)


if __name__ == "__main__":
    build().to_csv("data/sample_orders.csv", index=False)
    print("Wrote data/sample_orders.csv")
```

- [ ] **Step 4: Write `data/example_questions.json`**

These replace the LLM-generated suggestions that were cut from scope. Static, zero cost, shown as chips in the empty state.

```json
[
  "What is total revenue by region?",
  "Show monthly revenue over time",
  "Which category has the highest average profit margin?",
  "Compare average delivery days across channels",
  "What is the relationship between revenue and cost?",
  "Top 10 orders by profit",
  "Average rating by customer segment"
]
```

- [ ] **Step 5: Generate the CSV and swap out the old sample**

```bash
python scripts/generate_sample_data.py
git rm data/sample_data.csv
```

- [ ] **Step 6: Run and verify pass**

Run: `pytest tests/test_sample_data.py -v`
Expected: 4 passed. If `test_exercises_every_insight_kind` fails, adjust the planted magnitudes in the generator until every kind fires — do not weaken the test.

- [ ] **Step 7: Commit**

```bash
git add scripts/ data/ tests/test_sample_data.py
git commit -m "feat(data): reproducible synthetic sample dataset with planted findings"
```

---

## Task A12: No-code-execution guarantee, Docker, and full suite

**Files:**
- Modify: `tests/test_no_code_execution.py`
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Test: full suite

**Interfaces:**
- Consumes: everything
- Produces: a containerized backend and the test that enforces the project's central security claim

- [ ] **Step 1: Write the failing test**

```python
# tests/test_no_code_execution.py
import re
from pathlib import Path

BACKEND = Path("backend_app")
FORBIDDEN = re.compile(r"\b(exec|eval|compile)\s*\(")


def test_backend_contains_no_dynamic_code_execution():
    """The project's central claim: model output is never executed as code.

    If this fails, the README's security section is false. Fix the code,
    not the test.
    """
    offenders = []
    for path in BACKEND.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if FORBIDDEN.search(stripped):
                offenders.append(f"{path}:{lineno}: {stripped}")
    assert not offenders, "Dynamic code execution found:\n" + "\n".join(offenders)


def test_no_hardcoded_api_keys():
    pattern = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
    offenders = [
        str(p) for p in BACKEND.rglob("*.py")
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Possible hardcoded key in: {offenders}"
```

- [ ] **Step 2: Run and verify it passes**

Run: `pytest tests/test_no_code_execution.py -v`
Expected: PASS. Unlike other tasks this test should pass immediately — it is a guarantee, not a feature. To confirm it actually works, temporarily add `eval("1")` to `backend_app/main.py`, re-run and watch it fail, then remove it.

- [ ] **Step 3: Write the `Dockerfile`**

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend_app ./backend_app
COPY data ./data

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Single worker: session state is process-local by design. See README.
CMD ["uvicorn", "backend_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

- [ ] **Step 4: Write `docker-compose.yml` and `.dockerignore`**

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      SMARTANALYST_CORS_ORIGINS: '["http://localhost:5173"]'

  web:
    build:
      context: ./frontend_app
    ports: ["5173:5173"]
    environment:
      VITE_API_URL: http://localhost:8000
    depends_on: [api]
```

```
# .dockerignore
.git
.venv
venv
node_modules
tests
docs
__pycache__
*.pyc
frontend_app/node_modules
frontend_app/dist
```

- [ ] **Step 5: Run the full suite and the container**

```bash
pytest -v --cov=backend_app --cov-report=term-missing
ruff check .
docker build -t smartanalyst-api .
docker run --rm -p 8000:8000 smartanalyst-api
curl -s http://localhost:8000/health
```

Expected: all tests pass, ruff clean, `{"status":"ok"}` from the container.

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_code_execution.py Dockerfile docker-compose.yml .dockerignore
git commit -m "test(backend): enforce no-code-execution guarantee; add container"
```

**Phase A gate:** the backend is complete and independently testable here. Full suite green, container runs, `/health` responds. Review before starting Phase B.

---

# Phase B — Frontend

## Task B1: Retire CRA, scaffold Vite + TypeScript + Tailwind

**Files:**
- Delete: `frontend_app/src/App.css`, `App.test.js`, `ChatInterface.js`, `ChatInterface.css`, `FileUploader.js`, `logo.svg`, `reportWebVitals.js`, `setupTests.js`, `index.js`, `App.js`, `public/manifest.json`, `public/logo192.png`, `public/logo512.png`
- Create: `frontend_app/vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `tailwind.config.js`, `postcss.config.js`, `index.html`, `.env.example`, `src/main.tsx`, `src/App.tsx`, `src/index.css`
- Modify: `frontend_app/package.json`, `frontend_app/.gitignore`

**Interfaces:**
- Produces: a running Vite dev server on port 5173, `npm run build`, `npm run test`, `npm run lint`, `npm run typecheck`

- [ ] **Step 1: Replace `package.json`**

```json
{
  "name": "smartanalyst-web",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "lint": "eslint . --ext ts,tsx",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "react-dropzone": "^14.3.8",
    "recharts": "^2.15.3"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.18.0",
    "jsdom": "^26.0.0",
    "postcss": "^8.5.1",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.3",
    "vite": "^6.0.7",
    "vitest": "^3.0.2"
  }
}
```

`axios` is dropped — the native `fetch` API covers every call and removes a dependency.

- [ ] **Step 2: Delete CRA artifacts**

```bash
cd frontend_app
git rm src/App.css src/App.js src/App.test.js src/ChatInterface.js src/ChatInterface.css \
       src/FileUploader.js src/index.js src/logo.svg src/reportWebVitals.js src/setupTests.js \
       public/manifest.json public/logo192.png public/logo512.png
rm -rf node_modules package-lock.json
```

- [ ] **Step 3: Write the config files**

```ts
// vite.config.ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test-setup.ts" },
});
```

```js
// tailwind.config.js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: { extend: {} },
  plugins: [],
};
```

`tsconfig.json`: standard Vite React-TS template with `"strict": true`.
`index.html`: single `<div id="root">`, title "SmartAnalyst", no CRA boilerplate.
`.env.example`: `VITE_API_URL=http://localhost:8000`.

- [ ] **Step 4: Install and verify the dev server boots**

```bash
npm install
npm run build
npm run dev
```

Expected: build succeeds, dev server serves a page at `localhost:5173`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(frontend): retire CRA, scaffold Vite + TypeScript + Tailwind"
```

---

## Task B2: Typed API client and response types

**Files:**
- Create: `src/types.ts`, `src/api/client.ts`, `src/api/client.test.ts`, `src/test-setup.ts`

**Interfaces:**
- Produces: types mirroring every backend model; `ApiError` class carrying `status` and `detail`; client functions `health()`, `uploadDataset(file)`, `getProfile(id)`, `getInsights(id)`, `getCorrelations(id)`, `ask(id, question, apiKey)`

`types.ts` mirrors the Pydantic models exactly: `ColumnSchema`, `ColumnProfile`, `DatasetProfile`, `Insight`, `CorrelationMatrix`, `ChartSpec`, `UploadResponse`, `AskResponse`. Field names and optionality must match Tasks A4–A10 exactly — a mismatch here surfaces as a runtime `undefined`, not a type error, because the boundary is untyped JSON.

- [ ] **Step 1: Write the failing test**

```ts
// src/api/client.test.ts
import { describe, expect, it, vi } from "vitest";
import { ApiError, ask, getProfile } from "./client";

describe("api client", () => {
  it("throws ApiError carrying the server detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 400, json: async () => ({ detail: "Drop is not permitted." }),
    }));
    await expect(getProfile("abc")).rejects.toMatchObject({
      status: 400, detail: "Drop is not permitted.",
    });
  });

  it("sends the API key in the X-OpenAI-Key header and never in the URL", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal("fetch", spy);
    await ask("sid", "question", "sk-secret");
    const [url, init] = spy.mock.calls[0];
    expect(url).not.toContain("sk-secret");
    expect(init.headers["X-OpenAI-Key"]).toBe("sk-secret");
  });

  it("surfaces a network failure as an ApiError with status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getProfile("abc")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run: `npm test`
Expected: FAIL, module not found

- [ ] **Step 3: Implement `client.ts`**

A single `request<T>()` helper reading `import.meta.env.VITE_API_URL`, normalizing every failure into `ApiError { status, detail }` (status `0` for network errors, with a message that hints at backend cold start), and typed wrappers per endpoint.

- [ ] **Step 4: Run and verify pass**

Run: `npm test`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/types.ts src/api src/test-setup.ts
git commit -m "feat(frontend): typed API client with normalized errors"
```

---

## Task B3: App shell, theme, and cold-start handling

**Files:**
- Create: `src/App.tsx`, `src/components/TopBar.tsx`, `src/components/ColdStartBanner.tsx`, `src/hooks/useTheme.ts`, `src/lib/palette.ts`

**Interfaces:**
- Consumes: `api/client.health`
- Produces: three-region layout (top bar, left rail, main); `useTheme()` returning `{ theme, toggle }` persisted to localStorage and applying the `dark` class to `<html>`; `palette.ts` exporting `CHART_COLORS: string[]` (categorical, 8 hues, contrast-checked in both themes), `SEQUENTIAL: string[]`, and `DIVERGING: string[]` for the correlation heatmap

**Behaviour:** on mount, call `health()`. If it does not resolve within 3 seconds, show `ColdStartBanner` explaining that the free-tier backend is waking, with an elapsed counter, and keep retrying with backoff until it responds. This converts Render's 50-second cold start from apparent breakage into a handled state.

Charts and UI read from the same palette so nothing looks bolted on. Verify contrast in both themes before committing.

- [ ] **Step 1: Build the layout and theme hook**
- [ ] **Step 2: Build `ColdStartBanner` with the 3-second threshold and elapsed counter**
- [ ] **Step 3: Verify manually — start the frontend with the backend stopped, confirm the banner appears; start the backend, confirm it clears**
- [ ] **Step 4: Verify both themes at 1280px and 375px widths**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(frontend): app shell, theme toggle, and cold-start handling"
```

---

## Task B4: Upload, schema panel, and profile

**Files:**
- Create: `src/components/Dropzone.tsx`, `SchemaPanel.tsx`, `ProfileAccordion.tsx`, `EmptyState.tsx`, `src/hooks/useDataset.ts`, `src/lib/format.ts`

**Interfaces:**
- Consumes: `uploadDataset`, `getProfile`, `types.DatasetProfile`
- Produces: `useDataset()` returning `{ session, profile, insights, correlations, status, error, upload(file), loadSample() }`

**Behaviour:**
- Drag-and-drop plus click-to-browse via `react-dropzone` (finally using the dependency that has been installed and unused).
- Client-side rejection of non-CSV and over-10 MB files before upload, with the same wording the backend uses.
- `SchemaPanel` lists every column with a type icon, the semantic type, and a horizontal bar showing null percentage — so data quality is visible at a glance rather than buried in a table.
- `ProfileAccordion` expands a column to its full statistics: min/Q1/median/mean/Q3/max, std, skew, outlier count for numerics; top-5 values with frequency bars for categoricals.
- `EmptyState` offers "Load sample dataset" and renders the example-question chips from `data/example_questions.json`.
- No `alert()` anywhere. Every outcome is inline UI.

- [ ] **Step 1: Build `useDataset` and wire upload**
- [ ] **Step 2: Build `Dropzone` with client-side validation**
- [ ] **Step 3: Build `SchemaPanel` with null bars**
- [ ] **Step 4: Build `ProfileAccordion`**
- [ ] **Step 5: Build `EmptyState` with sample load and question chips**
- [ ] **Step 6: Verify manually against a running backend using `data/sample_orders.csv`**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(frontend): dataset upload, schema panel, and column profile"
```

---

## Task B5: Insights panel and correlation heatmap

**Files:**
- Create: `src/components/InsightsPanel.tsx`, `src/components/CorrelationHeatmap.tsx`

**Interfaces:**
- Consumes: `getInsights`, `getCorrelations`, `types.Insight`, `types.CorrelationMatrix`, `palette.DIVERGING`

**Behaviour:**
- Findings render as cards grouped by severity, each with an icon, the title, the detail line, and the columns involved as chips. Clicking a column chip scrolls the schema panel to it.
- The heatmap uses a diverging scale centred at zero — negative and positive correlation must be visually distinct, not two shades of the same hue. Cell labels show the coefficient to two decimals; cells are keyboard-focusable with an accessible label, because a colour-only encoding excludes colour-blind viewers.
- Both panels render with no API key present. This is the point: a first-time visitor sees real analysis immediately.

- [ ] **Step 1: Build `InsightsPanel` grouped by severity**
- [ ] **Step 2: Build `CorrelationHeatmap` with a diverging scale and text labels**
- [ ] **Step 3: Verify colour-blind legibility — check that the value labels alone convey the data**
- [ ] **Step 4: Verify both themes**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(frontend): insights panel and correlation heatmap"
```

---

## Task B6: Conversation, answer card, and chart rendering

**Files:**
- Create: `src/components/Conversation.tsx`, `AnswerCard.tsx`, `ChartView.tsx`, `TableView.tsx`, `SqlView.tsx`, `LoadingSteps.tsx`, `ErrorCard.tsx`, `ApiKeyDialog.tsx`, `src/hooks/useConversation.ts`, `src/hooks/useApiKey.ts`
- Test: `src/components/ChartView.test.tsx`, `src/hooks/useApiKey.test.ts`

**Interfaces:**
- Consumes: `ask`, `types.AskResponse`, `types.ChartSpec`, `palette.CHART_COLORS`
- Produces: `useApiKey()` returning `{ key, setKey, clear, hasKey }` backed by **sessionStorage only**; `useConversation(sessionId)` returning `{ turns, phase, error, submit(question), retry() }` where `phase` is `"idle" | "generating" | "running" | "rendering"`

**Behaviour:**
- `ChartView` switches on `spec.kind` and renders the matching Recharts component. `table` renders `TableView` instead. Every chart: responsive container, gridlines at low contrast, axis labels, a tooltip with formatted values, and a legend only when more than one series exists.
- `TableView` is sortable by column and paginated at 50 rows, with a truncation notice when the backend flagged `truncated`.
- `SqlView` shows the generated SQL in a monospace block with a copy button. This is the tab a reviewer clicks — it must look good.
- `LoadingSteps` advances through generating → running → rendering. The phases are driven by the request lifecycle, not a timer.
- `ErrorCard` shows the failure detail and, when the failure was a rejected or broken query, the SQL that caused it plus a retry action.
- `ApiKeyDialog` opens on the first question attempt without a key, states plainly that the key is held in the browser session and never sent anywhere but OpenAI via the backend proxy, and links to where to get one.

- [ ] **Step 1: Write the failing tests**

```tsx
// src/components/ChartView.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChartView from "./ChartView";

const rows = [{ region: "North", total: 100 }, { region: "South", total: 200 }];

describe("ChartView", () => {
  it("renders a table when the spec kind is table", () => {
    render(<ChartView spec={{ kind: "table", y: [], title: "T" }} rows={rows}
                      columns={["region", "total"]} truncated={false} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders a chart surface for a bar spec", () => {
    const { container } = render(
      <ChartView spec={{ kind: "bar", x: "region", y: ["total"], title: "T" }}
                 rows={rows} columns={["region", "total"]} truncated={false} />
    );
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("shows an empty message rather than a blank chart for no rows", () => {
    render(<ChartView spec={{ kind: "bar", x: "region", y: ["total"], title: "T" }}
                      rows={[]} columns={["region", "total"]} truncated={false} />);
    expect(screen.getByText(/no rows/i)).toBeInTheDocument();
  });
});
```

```ts
// src/hooks/useApiKey.test.ts
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useApiKey } from "./useApiKey";

describe("useApiKey", () => {
  beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });

  it("persists to sessionStorage, never localStorage", () => {
    const { result } = renderHook(() => useApiKey());
    act(() => result.current.setKey("sk-abc"));
    expect(sessionStorage.getItem("smartanalyst:key")).toBe("sk-abc");
    expect(localStorage.length).toBe(0);
  });

  it("clears the key", () => {
    const { result } = renderHook(() => useApiKey());
    act(() => result.current.setKey("sk-abc"));
    act(() => result.current.clear());
    expect(result.current.hasKey).toBe(false);
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run: `npm test`
Expected: FAIL

- [ ] **Step 3: Build the hooks, then the components in the order listed above**
- [ ] **Step 4: Run and verify pass**

Run: `npm test && npm run typecheck && npm run build`
Expected: all green

- [ ] **Step 5: Verify end to end against the running backend — upload the sample, ask three of the example questions, check all three tabs and both export buttons**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(frontend): conversation with chart, table, and SQL views"
```

**Phase B gate:** the full application runs locally via `docker compose up`. Review before Phase C.

---

# Phase C — Repository and deployment

## Task C1: Continuous integration

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a workflow running on push and pull request with two jobs

The backend job: Python 3.11, install `requirements-dev.txt`, run `ruff check .`, then `pytest --cov=backend_app`. The frontend job: Node 22, `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

Both jobs must be required for the branch to be considered green. The README badge points at this workflow.

- [ ] **Step 1: Write the workflow**
- [ ] **Step 2: Verify locally by running each job's commands in sequence**
- [ ] **Step 3: Commit**

```bash
git commit -m "ci: lint, type-check, and test both applications"
```

---

## Task C2: README, LICENSE, and architecture diagram

**Files:**
- Rewrite: `README.md`
- Create: `LICENSE` (MIT, 2026, Parth Patel), `docs/architecture.svg`

The README is the artifact most reviewers actually read. Sections, in order:

1. **Title, one-line description, badges** — CI status, Python version, licence, live demo link.
2. **Hero** — the existing `banner.png`, then an animated GIF of a real question producing a chart. The GIF matters more than any paragraph.
3. **What it does** — three sentences, no marketing language.
4. **Live demo** — link, plus the note that profiling and insights need no API key and only natural-language questions do.
5. **Why SQL instead of generated Python** — short section explaining that the tool generates validated DuckDB SQL rather than executing model-written code, and what that rules out. This is the strongest technical signal in the repository and it belongs above the fold, not in an appendix.
6. **Features** — profiling with semantic type inference, deterministic insights, correlation analysis, natural-language questions with conversation memory, interactive charts with visible SQL.
7. **Architecture** — the SVG diagram plus a short request walkthrough.
8. **Quickstart** — `docker compose up`, then the manual path for each app.
9. **API reference** — a table of the six endpoints with methods and purposes.
10. **Security** — the seven controls from the spec, stated plainly, including that the AST guard replaced a string-prefix check and why the difference matters.
11. **Known limitations** — single-worker in-memory sessions, 10 MB upload cap, SQL-expressible questions only, free-tier cold start. Stated openly. A reviewer trusts a project that names its own edges.
12. **Tech stack** and **local development** — including how to regenerate the sample dataset.

- [ ] **Step 1: Draw `docs/architecture.svg` — browser, API, DuckDB, OpenAI, with the guard shown on the path between the model and the database**
- [ ] **Step 2: Record the demo GIF: upload sample → insights appear → ask "monthly revenue over time" → chart renders → open the SQL tab**
- [ ] **Step 3: Write the README**
- [ ] **Step 4: Add the MIT LICENSE**
- [ ] **Step 5: Verify every command in the quickstart by running it from a clean clone**
- [ ] **Step 6: Commit**

```bash
git commit -m "docs: rewrite README with architecture, security, and limitations"
```

---

## Task C3: Deployment configuration

**Files:**
- Create: `render.yaml`, `frontend_app/vercel.json`

**Interfaces:**
- Produces: a Render web service building from the root Dockerfile with `SMARTANALYST_CORS_ORIGINS` set to the Vercel origin, and a Vercel static build from `frontend_app` with `VITE_API_URL` set to the Render URL

Deployment involves creating accounts and services on external platforms. **Do not deploy without the owner performing or explicitly authorizing each step** — this task prepares the configuration and documents the sequence; the owner executes it.

- [ ] **Step 1: Write `render.yaml` and `vercel.json`**
- [ ] **Step 2: Document the deploy sequence in the README, including the CORS origin that must be set after the Vercel URL exists**
- [ ] **Step 3: Commit**

```bash
git commit -m "chore: add Render and Vercel deployment configuration"
```

---

## Task C4: Final review and push

- [ ] **Step 1: Run the complete verification**

```bash
pytest -v --cov=backend_app && ruff check . && cd frontend_app && npm run lint && npm run typecheck && npm test && npm run build
```

- [ ] **Step 2: Read the full diff against `master`**

```bash
git diff master...feat/portfolio-rebuild --stat
```

- [ ] **Step 3: Confirm no secrets are present**

```bash
git diff master...feat/portfolio-rebuild | grep -nE "sk-[A-Za-z0-9_-]{16,}"
```

Expected: no output.

- [ ] **Step 4: Present the diff to the owner and obtain explicit approval to push.** Nothing reaches `origin` before this.

- [ ] **Step 5: Push only after approval**

```bash
git push -u origin feat/portfolio-rebuild
```

Then open a pull request into `master`, or merge locally and push `master` — the owner's choice.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: architecture → A1/A9/A10; session model → A4; security model's seven controls → A1 (config, redaction), A2 (AST guard), A3 (external access off, row limits), A8 (key not echoed), A12 (no-exec test); column profile → A5; auto-insights → A6; correlations → A5; ask pipeline → A8/A10; chart spec and fallback → A7; frontend layout and states → B3–B6; testing → every task plus A12; repo deliverables → A11, A12, C1–C3; commit strategy → the per-task commits; risks → cold start in B3, guard failures in A2/A10, BYOK-optional analysis asserted in A9's final test.

**Two gaps found and closed while reviewing:** the spec's "export chart PNG" was unassigned — it now sits in B6's AnswerCard. The spec's static example questions had no home — they are now `data/example_questions.json`, created in A11 and consumed in B4.

**One ordering hazard, flagged in place:** A4's `SessionStore.create` calls `build_schema`, which A5 defines. A4 Step 4 notes the stub-or-reorder option rather than leaving the implementer to discover the cycle.

**Type consistency.** `ChartSpec` fields (`kind`, `x`, `y`, `series`, `title`) are identical in A7, A10, B2, and B6. `QueryResult` fields match between A3, A7, and A10. `Insight` fields match between A6, A9, and B5. `session_id` is the path parameter name in A9, A10, and B2. `X-OpenAI-Key` is spelled identically in A1's CORS config, A10's header alias, and B2's client test.

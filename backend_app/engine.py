"""DuckDB execution layer.

Every query reaching the database has passed :func:`sql_guard.validate`
first. The connection is additionally hardened so that even a query that
somehow evaded the guard cannot reach the filesystem or the network.
"""

import math
import re
from dataclasses import dataclass
from typing import Any

import duckdb
import pandas as pd

from backend_app.sql_guard import validate

TABLE_NAME = "data"

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class QueryResult:
    """A query and what it returned.

    ``sql`` is the normalized form that actually executed, not the raw model
    output, so what the user is shown is what ran.
    """

    sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool


def create_connection(df: pd.DataFrame, table: str = TABLE_NAME) -> duckdb.DuckDBPyConnection:
    """Load a dataframe into a fresh in-memory database.

    External access is disabled before the data is loaded, which blocks
    ``read_csv``, ``httpfs``, and every other route out to the host. The SQL
    guard blocks those functions too; this is the layer that holds if the
    guard is ever weakened by a refactor.
    """
    if not _IDENTIFIER.match(table):
        raise ValueError(f"Not a valid table identifier: {table!r}")

    conn = duckdb.connect(database=":memory:")
    conn.execute("SET enable_external_access = false")
    conn.register("_incoming", df)
    # The identifier is checked against _IDENTIFIER above and cannot carry SQL.
    conn.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _incoming')  # noqa: S608
    conn.unregister("_incoming")
    return conn


def _jsonable(value: Any) -> Any:
    """Convert a DuckDB scalar into something the JSON encoder accepts."""
    if value is None:
        return None
    if isinstance(value, float):
        # NaN and infinity are not valid JSON; null is the honest encoding.
        return None if math.isnan(value) or math.isinf(value) else value
    if value is pd.NaT:
        return None
    if isinstance(value, bool):
        return value
    # numpy scalars expose .item(); pandas Timestamps do not and are left alone
    # for the JSON encoder to render as ISO-8601.
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, pd.Timestamp):
        try:
            return item()
        except (ValueError, AttributeError):
            return value
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def run_query(
    conn: duckdb.DuckDBPyConnection, sql: str, *, row_limit: int
) -> QueryResult:
    """Validate, execute, and return at most ``row_limit`` rows.

    One row beyond the limit is fetched so truncation can be reported without
    a second counting query. Rows are taken through the cursor rather than by
    wrapping the query in ``SELECT * FROM (...) LIMIT n``: a subquery wrapper
    is not guaranteed to preserve an ORDER BY the query carries itself.
    """
    safe_sql = validate(sql)

    cursor = conn.execute(safe_sql)
    columns = [description[0] for description in cursor.description or []]
    records = cursor.fetchmany(int(row_limit) + 1)

    truncated = len(records) > row_limit
    if truncated:
        records = records[:row_limit]

    rows = [
        {column: _jsonable(value) for column, value in zip(columns, record, strict=False)}
        for record in records
    ]

    return QueryResult(
        sql=safe_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )

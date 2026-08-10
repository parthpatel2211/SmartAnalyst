"""AST-based validation for model-generated SQL.

This module is the security boundary for the whole application. SmartAnalyst
never executes model-written code; it executes model-written *queries*, and
this is what decides whether a query is safe to run.

The previous implementation checked ``sql.lower().startswith("select")``.
That check has two defects, both exercised in the test suite:

* ``"select 1; drop table data"`` passes it, because only the first token is
  inspected.
* Lowercasing the query also lowercases string literals, so
  ``WHERE region = 'North'`` silently became ``'north'`` and matched nothing.

Validation here is structural instead. The query is parsed, and it must be
exactly one statement, rooted in a read-only node, containing no forbidden
node and no file-reading function anywhere in its tree.
"""

import sqlglot
from sqlglot import exp

DIALECT = "duckdb"

#: Statement types that only read. Note that ``WITH ... SELECT`` parses as a
#: ``Select`` carrying a ``With``, so it needs no separate entry.
ALLOWED_ROOTS = (
    exp.Select,
    exp.Union,
    exp.Except,
    exp.Intersect,
    exp.Subquery,
)

#: Rejected anywhere in the tree, not merely at the root. A CTE can wrap a
#: ``DELETE ... RETURNING`` and still present a ``Select`` root, so the root
#: check alone would let it through.
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Attach,
    exp.Detach,
    exp.Copy,
    exp.Pragma,
    exp.Set,
    exp.Use,
    exp.Grant,
    exp.Command,
)

#: Blocked regardless of DuckDB's ``enable_external_access`` setting. The
#: connection already disables external access; this is the second layer, so
#: a configuration mistake alone cannot expose the filesystem.
FORBIDDEN_FUNCTIONS = frozenset(
    {
        "read_csv",
        "read_csv_auto",
        "read_parquet",
        "read_json",
        "read_json_auto",
        "read_ndjson",
        "read_ndjson_auto",
        "read_text",
        "read_blob",
        "read_xlsx",
        "glob",
        "parquet_scan",
        "csv_scan",
        "iceberg_scan",
        "delta_scan",
        "postgres_scan",
        "postgres_query",
        "sqlite_scan",
        "mysql_scan",
        "mysql_query",
        "shell",
    }
)


class SqlValidationError(ValueError):
    """Raised when generated SQL is not a single, read-only query."""


def _function_names(node: exp.Expression) -> set[str]:
    """Every name a function node could be known by, lowercased.

    Two mechanisms have to be covered. Most functions parse to
    :class:`exp.Anonymous`, whose ``name`` is the function name. Some are
    promoted to first-class nodes -- ``read_csv`` becomes ``exp.ReadCSV``,
    whose ``name`` is the *file path*, not the function. Which functions get
    promoted is a sqlglot version detail, so both paths are checked rather
    than relying on either one holding still across upgrades.
    """
    names: set[str] = set()
    if isinstance(node, exp.Anonymous):
        names.add((node.name or "").lower())
    if isinstance(node, exp.Func):
        try:
            names.update(n.lower() for n in type(node).sql_names())
        except Exception:  # noqa: BLE001 - a node without sql_names is simply not a match
            pass
    return names


def validate(sql: str) -> str:
    """Return normalized SQL, or raise :class:`SqlValidationError`.

    The returned string is the re-serialized parse tree, which is what should
    be executed and what should be shown to the user, so that the query they
    see is exactly the query that ran.
    """
    if not sql or not sql.strip():
        raise SqlValidationError("The query is empty.")

    try:
        statements = [s for s in sqlglot.parse(sql, dialect=DIALECT) if s is not None]
    except Exception as err:
        raise SqlValidationError(f"Could not parse that as SQL: {err}") from err

    if not statements:
        raise SqlValidationError("The query is empty.")

    if len(statements) > 1:
        raise SqlValidationError(
            f"Expected a single statement but found {len(statements)}. "
            "Multiple statements are not permitted."
        )

    statement = statements[0]

    if not isinstance(statement, ALLOWED_ROOTS):
        raise SqlValidationError(
            f"{type(statement).__name__} statements are not permitted. "
            "Only read-only SELECT and WITH queries can be run."
        )

    for node in statement.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlValidationError(
                f"{type(node).__name__} is not permitted anywhere in the query."
            )
        forbidden = _function_names(node) & FORBIDDEN_FUNCTIONS
        if forbidden:
            raise SqlValidationError(
                f"The function {sorted(forbidden)[0]}() is not permitted; it can "
                "read data from outside the uploaded dataset."
            )

    return statement.sql(dialect=DIALECT)

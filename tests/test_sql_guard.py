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
    "SELECT category, AVG(profit) AS avg_profit FROM data GROUP BY category HAVING AVG(profit) > 10",
    "SELECT DATE_TRUNC('month', order_date) AS m, SUM(revenue) FROM data GROUP BY 1 ORDER BY 1",
    # Models routinely emit a trailing semicolon; one statement is still one
    # statement, and it is normalized away.
    "SELECT * FROM data;",
    "SELECT * FROM data;   ",
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
    "CREATE VIEW v AS SELECT * FROM data",
    # Multi-statement smuggling -- the bug in the original codebase
    "SELECT 1; DROP TABLE data",
    "SELECT 1;DROP TABLE data;",
    "SELECT 1; -- harmless\nDROP TABLE data",
    # Filesystem and extension escape
    "ATTACH 'evil.db' AS evil",
    "DETACH evil",
    "COPY data TO '/tmp/out.csv'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "PRAGMA database_list",
    "SET memory_limit = '100GB'",
    # File-reading functions, blocked independently of external-access config
    "SELECT * FROM read_csv_auto('/etc/passwd')",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
    "SELECT * FROM glob('/**')",
    # A file-reading call buried in a subquery rather than the top-level FROM
    "SELECT * FROM data WHERE region IN (SELECT * FROM read_csv_auto('/etc/passwd'))",
    # DML hidden inside a CTE: root node is a Select, so the root check alone
    # is not enough -- the whole tree has to be walked.
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


def test_error_names_the_offending_function():
    with pytest.raises(SqlValidationError) as exc:
        validate("SELECT * FROM read_csv_auto('/etc/passwd')")
    assert "read_csv_auto" in str(exc.value)


def test_returns_normalized_sql_that_still_parses():
    out = validate("select   region ,  sum(revenue) as t from data group by region")
    assert validate(out) == out


def test_trailing_semicolon_is_stripped_from_the_returned_query():
    assert validate("SELECT * FROM data;") == "SELECT * FROM data"


@pytest.mark.parametrize(
    "sql",
    [
        # Case variation and quoting must not get past the function denylist.
        "select * from READ_CSV_AUTO('/etc/passwd')",
        'SELECT * FROM "read_csv_auto"(\'/etc/passwd\')',
        # A forbidden call reached through a UNION branch or a nested subquery.
        "SELECT * FROM data UNION ALL SELECT * FROM read_csv_auto('/x')",
        "SELECT * FROM (SELECT * FROM (SELECT * FROM read_parquet('/x')))",
        "SELECT * FROM data WHERE region = (SELECT * FROM glob('/**'))",
        # A block comment before the second statement.
        "SELECT * FROM data WHERE 1=1 /* c */; DROP TABLE data",
        # COPY wrapping a legitimate SELECT.
        "COPY (SELECT 1) TO '/tmp/x.csv'",
        # DML in a second CTE, behind a harmless first one.
        "WITH a AS (SELECT 1), b AS (INSERT INTO data VALUES (1) RETURNING *) SELECT * FROM a",
        # Cross-database readers.
        "SELECT * FROM sqlite_scan('a.db','t')",
        "SELECT * FROM postgres_query('db','SELECT 1')",
        # Statements sqlglot cannot model, which fall back to Command.
        "EXPLAIN SELECT * FROM data",
        "CALL pragma_version()",
    ],
)
def test_rejects_evasion_attempts(sql):
    """Bypasses attempted against the guard after the first suite passed.

    Kept as regression cover: each of these targets a different assumption
    the guard makes, so a future refactor that weakens one shows up here.
    """
    with pytest.raises(SqlValidationError):
        validate(sql)

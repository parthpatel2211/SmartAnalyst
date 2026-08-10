import datetime as dt

import duckdb
import pandas as pd
import pytest

from backend_app.engine import create_connection, run_query
from backend_app.sql_guard import SqlValidationError


@pytest.fixture
def conn():
    df = pd.DataFrame(
        {
            "region": ["North", "South", "North"],
            "revenue": [10, 20, 30],
        }
    )
    return create_connection(df)


def test_runs_a_grouped_query(conn):
    result = run_query(
        conn,
        "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
        row_limit=100,
    )
    assert result.row_count == 2
    assert set(result.columns) == {"region", "total"}
    assert {r["region"]: r["total"] for r in result.rows} == {"North": 40, "South": 20}


def test_case_sensitive_string_filter_still_matches(conn):
    """Regression: the old code lowercased the query, so 'North' became 'north'."""
    result = run_query(conn, "SELECT * FROM data WHERE region = 'North'", row_limit=100)
    assert result.row_count == 2


def test_dangerous_sql_is_rejected_before_execution(conn):
    with pytest.raises(SqlValidationError):
        run_query(conn, "DROP TABLE data", row_limit=100)
    # The table is still there, which is the point.
    assert run_query(conn, "SELECT COUNT(*) AS n FROM data", row_limit=10).rows[0]["n"] == 3


def test_row_limit_truncates_and_flags(conn):
    result = run_query(conn, "SELECT * FROM data", row_limit=2)
    assert result.row_count == 2
    assert result.truncated is True


def test_result_at_exactly_the_limit_is_not_flagged_truncated(conn):
    result = run_query(conn, "SELECT * FROM data", row_limit=3)
    assert result.row_count == 3
    assert result.truncated is False


def test_ordering_survives_the_row_limit(conn):
    """A query carrying its own ORDER BY must not be reordered by limiting."""
    result = run_query(conn, "SELECT revenue FROM data ORDER BY revenue DESC", row_limit=2)
    assert [r["revenue"] for r in result.rows] == [30, 20]


def test_inner_limit_is_respected(conn):
    result = run_query(
        conn, "SELECT revenue FROM data ORDER BY revenue DESC LIMIT 1", row_limit=100
    )
    assert result.row_count == 1
    assert result.rows[0]["revenue"] == 30


def test_external_file_access_is_disabled_on_the_connection(conn):
    """Second layer: even bypassing the guard, the connection cannot read files.

    Asserting PermissionException specifically, rather than any failure, is
    what proves the block comes from the disabled-external-access setting and
    not from an unrelated error such as a typo in the function name.
    """
    with pytest.raises(duckdb.PermissionException):
        conn.execute("SELECT * FROM read_csv_auto('/etc/passwd')").fetchall()


def test_table_identifier_is_validated():
    with pytest.raises(ValueError, match="valid table identifier"):
        create_connection(pd.DataFrame({"a": [1]}), table='x" AS SELECT 1; DROP TABLE y --')


def test_nan_becomes_none_for_json():
    conn = create_connection(pd.DataFrame({"x": [1.0, None]}))
    result = run_query(conn, "SELECT * FROM data ORDER BY x NULLS LAST", row_limit=10)
    assert result.rows[0]["x"] == 1.0
    assert result.rows[1]["x"] is None


def test_values_are_json_serializable():
    """Rows go straight into a JSON response, so numpy scalars would break it."""
    import json

    df = pd.DataFrame(
        {
            "when": pd.to_datetime(["2024-01-01", "2024-06-15"]),
            "count": [1, 2],
            "amount": [1.5, 2.5],
            "label": ["a", "b"],
            "flag": [True, False],
        }
    )
    result = run_query(create_connection(df), "SELECT * FROM data", row_limit=10)
    encoded = json.dumps(result.rows, default=str)
    assert "2024-01-01" in encoded
    assert isinstance(result.rows[0]["count"], int)
    assert isinstance(result.rows[0]["amount"], float)
    assert isinstance(result.rows[0]["flag"], bool)
    assert isinstance(result.rows[0]["when"], dt.date | str)


def test_empty_result_is_handled(conn):
    result = run_query(conn, "SELECT * FROM data WHERE region = 'Nowhere'", row_limit=10)
    assert result.row_count == 0
    assert result.rows == []
    assert result.truncated is False
    assert result.columns == ["region", "revenue"]


def test_returned_sql_is_the_normalized_query_that_ran(conn):
    result = run_query(conn, "select   region from data", row_limit=10)
    assert result.sql == "SELECT region FROM data"


def test_a_broken_query_raises_rather_than_returning_empty(conn):
    with pytest.raises(duckdb.BinderException):
        run_query(conn, "SELECT no_such_column FROM data", row_limit=10)

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from backend_app.sessions import (
    SessionNotFound,
    SessionStore,
    UploadTooLarge,
    read_csv_limited,
)

DF = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.fixture
def store():
    return SessionStore(ttl_seconds=1800, max_sessions=5)


def test_create_and_get_roundtrip(store):
    session = store.create(DF, name="test.csv")
    assert store.get(session.id) is session
    assert {c.name for c in session.schema} == {"a", "b"}


def test_each_session_gets_its_own_id_and_data(store):
    """The original code held one global dataframe shared by every caller."""
    first = store.create(pd.DataFrame({"x": [1]}), name="one.csv")
    second = store.create(pd.DataFrame({"y": [2, 3]}), name="two.csv")
    assert first.id != second.id
    assert len(first.df) == 1
    assert len(second.df) == 2
    assert [c.name for c in second.schema] == ["y"]


def test_unknown_session_raises(store):
    with pytest.raises(SessionNotFound):
        store.get("nope")


def test_expired_session_is_evicted(store):
    session = SessionStore(ttl_seconds=60, max_sessions=5)
    created = session.create(DF, name="t.csv")
    created.last_used_at = datetime.now(UTC) - timedelta(seconds=120)
    with pytest.raises(SessionNotFound):
        session.get(created.id)


def test_lru_cap_evicts_the_oldest(store):
    small = SessionStore(ttl_seconds=1800, max_sessions=2)
    first = small.create(DF, name="1.csv")
    small.create(DF, name="2.csv")
    small.create(DF, name="3.csv")
    assert len(small) == 2
    with pytest.raises(SessionNotFound):
        small.get(first.id)


def test_get_refreshes_last_used(store):
    session = store.create(DF, name="t.csv")
    session.last_used_at = datetime.now(UTC) - timedelta(seconds=100)
    stale = session.last_used_at
    store.get(session.id)
    assert session.last_used_at > stale


def test_recently_used_session_survives_the_lru_cap():
    small = SessionStore(ttl_seconds=1800, max_sessions=2)
    first = small.create(DF, name="1.csv")
    second = small.create(DF, name="2.csv")
    small.get(first.id)  # first is now the most recently used
    small.create(DF, name="3.csv")
    assert small.get(first.id) is first
    with pytest.raises(SessionNotFound):
        small.get(second.id)


def test_session_query_connection_works(store):
    session = store.create(DF, name="t.csv")
    assert session.conn.execute("SELECT COUNT(*) FROM data").fetchone()[0] == 3


def test_history_keeps_only_the_last_three_turns(store):
    session = store.create(DF, name="t.csv")
    for i in range(5):
        session.add_turn(question=f"q{i}", sql=f"SELECT {i}", summary=f"s{i}")
    assert len(session.history) == 3
    assert [t.question for t in session.history] == ["q2", "q3", "q4"]


# --------------------------------------------------------------------------
# Upload limits
# --------------------------------------------------------------------------


def test_reads_a_valid_csv():
    frame = read_csv_limited(b"a,b\n1,2\n3,4\n", max_bytes=10_000, max_rows=1000)
    assert list(frame.columns) == ["a", "b"]
    assert len(frame) == 2


def test_rejects_oversized_upload():
    with pytest.raises(UploadTooLarge):
        read_csv_limited(b"a,b\n1,2\n" * 100, max_bytes=10, max_rows=1000)


def test_rejects_too_many_rows():
    raw = ("a\n" + "1\n" * 50).encode()
    with pytest.raises(UploadTooLarge):
        read_csv_limited(raw, max_bytes=10_000, max_rows=10)


def test_accepts_a_file_exactly_at_the_row_limit():
    raw = ("a\n" + "1\n" * 10).encode()
    assert len(read_csv_limited(raw, max_bytes=10_000, max_rows=10)) == 10


def test_rejects_an_empty_file():
    with pytest.raises(UploadTooLarge):
        read_csv_limited(b"", max_bytes=10_000, max_rows=1000)


def test_rejects_a_header_only_file():
    with pytest.raises(UploadTooLarge):
        read_csv_limited(b"a,b\n", max_bytes=10_000, max_rows=1000)


# --------------------------------------------------------------------------
# Datetime coercion
# --------------------------------------------------------------------------


def test_date_column_becomes_a_real_datetime():
    """Left as text, a date column costs the tool its time axis: no DATE_TRUNC
    in DuckDB, no line charts, and the model told the column is free text."""
    raw = b"order_date,revenue\n2024-01-01,10\n2024-02-01,20\n2024-03-01,30\n"
    frame = read_csv_limited(raw, max_bytes=10_000, max_rows=1000)
    assert pd.api.types.is_datetime64_any_dtype(frame["order_date"])


def test_slash_separated_dates_are_parsed():
    raw = b"d,v\n01/15/2024,1\n02/20/2024,2\n03/25/2024,3\n"
    frame = read_csv_limited(raw, max_bytes=10_000, max_rows=1000)
    assert pd.api.types.is_datetime64_any_dtype(frame["d"])


def test_numeric_columns_are_not_turned_into_dates():
    """A year, a postcode, and an ID are all bare numbers, not timestamps."""
    raw = b"year,postcode,amount\n2024,90210,15\n2023,10001,20\n2022,60601,25\n"
    frame = read_csv_limited(raw, max_bytes=10_000, max_rows=1000)
    for column in ("year", "postcode", "amount"):
        assert not pd.api.types.is_datetime64_any_dtype(frame[column]), column


def test_category_labels_are_not_turned_into_dates():
    raw = b"region,v\nNorth,1\nSouth,2\nEast,3\n"
    frame = read_csv_limited(raw, max_bytes=10_000, max_rows=1000)
    assert not pd.api.types.is_datetime64_any_dtype(frame["region"])


def test_mostly_unparseable_column_is_left_alone():
    raw = b"note,v\n2024-01-01,1\nnot a date,2\nalso not,3\nnope,4\n"
    frame = read_csv_limited(raw, max_bytes=10_000, max_rows=1000)
    assert not pd.api.types.is_datetime64_any_dtype(frame["note"])


def test_coerced_dates_reach_duckdb_as_timestamps():
    """DATE_TRUNC is what makes 'revenue by month' answerable at all."""
    raw = b"order_date,revenue\n2024-01-05,10\n2024-01-20,20\n2024-02-03,30\n"
    store = SessionStore(ttl_seconds=1800, max_sessions=5)
    session = store.create(read_csv_limited(raw, max_bytes=10_000, max_rows=1000), name="t.csv")
    rows = session.conn.execute(
        "SELECT DATE_TRUNC('month', order_date) AS m, SUM(revenue) AS total "
        "FROM data GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][1] == 30


def test_size_error_message_states_the_limit():
    with pytest.raises(UploadTooLarge) as exc:
        read_csv_limited(b"x" * 100, max_bytes=50, max_rows=1000)
    assert "MB" in str(exc.value)

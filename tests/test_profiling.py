import numpy as np
import pandas as pd
import pytest

from backend_app.profiling import (
    build_schema,
    correlations,
    infer_semantic_type,
    profile_dataset,
)


@pytest.fixture
def frame():
    rng = np.random.default_rng(42)
    n = 200
    revenue = rng.gamma(shape=2.0, scale=100.0, size=n)  # right-skewed
    return pd.DataFrame(
        {
            "order_id": range(1, n + 1),
            "order_date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "region": rng.choice(["North", "South", "East", "West"], n),
            "revenue": revenue,
            "cost": revenue * 0.6 + rng.normal(0, 5, n),  # strongly correlated
            "is_returned": rng.choice([True, False], n),
            "rating": np.where(rng.random(n) < 0.3, np.nan, rng.integers(1, 6, n)),
            "constant": ["same"] * n,
        }
    )


def test_infers_semantic_types(frame):
    types = {c.name: c.semantic_type for c in build_schema(frame)}
    assert types["order_id"] == "id"
    assert types["order_date"] == "datetime"
    assert types["region"] == "categorical"
    assert types["revenue"] == "numeric"
    assert types["is_returned"] == "boolean"


def test_schema_reports_nulls_and_distinct_counts(frame):
    schema = {c.name: c for c in build_schema(frame)}
    assert schema["region"].distinct_count == 4
    assert schema["revenue"].null_pct == 0.0
    assert schema["rating"].null_pct > 0


def test_profile_reports_dataset_shape(frame):
    profile = profile_dataset(frame)
    assert profile.row_count == 200
    assert profile.column_count == 8
    assert profile.duplicate_rows == 0
    assert profile.memory_bytes > 0


def test_numeric_column_has_full_statistics(frame):
    revenue = next(c for c in profile_dataset(frame).columns if c.name == "revenue")
    assert revenue.min is not None and revenue.max is not None
    assert revenue.q1 < revenue.median < revenue.q3
    assert revenue.skew > 0.5, "gamma-distributed revenue should be right-skewed"
    assert revenue.outlier_count is not None and revenue.outlier_count >= 0
    assert revenue.min <= revenue.q1 and revenue.q3 <= revenue.max


def test_categorical_column_has_no_numeric_statistics(frame):
    region = next(c for c in profile_dataset(frame).columns if c.name == "region")
    assert region.median is None
    assert region.skew is None


def test_null_percentage_is_reported(frame):
    rating = next(c for c in profile_dataset(frame).columns if c.name == "rating")
    assert 20 < rating.null_pct < 40


def test_top_values_are_ranked(frame):
    region = next(c for c in profile_dataset(frame).columns if c.name == "region")
    assert len(region.top_values) <= 5
    counts = [v.count for v in region.top_values]
    assert counts == sorted(counts, reverse=True)


def test_constant_column_has_one_distinct_value(frame):
    constant = next(c for c in profile_dataset(frame).columns if c.name == "constant")
    assert constant.distinct_count == 1


def test_correlations_find_the_planted_relationship(frame):
    matrix = correlations(frame)
    pair = next(p for p in matrix.pairs if {p.x, p.y} == {"revenue", "cost"})
    assert pair.value > 0.9


def test_correlation_pairs_are_ranked_by_absolute_strength(frame):
    values = [abs(p.value) for p in correlations(frame).pairs]
    assert values == sorted(values, reverse=True)


def test_correlations_ignore_non_numeric_columns(frame):
    assert "region" not in correlations(frame).columns


def test_correlations_ignore_identifier_columns(frame):
    """An id correlates with row order, which is not a finding."""
    assert "order_id" not in correlations(frame).columns


def test_correlation_matrix_is_square_and_diagonal_is_one(frame):
    matrix = correlations(frame)
    size = len(matrix.columns)
    assert all(len(row) == size for row in matrix.matrix)
    for i in range(size):
        assert matrix.matrix[i][i] == pytest.approx(1.0)


def test_empty_numeric_set_returns_empty_matrix():
    matrix = correlations(pd.DataFrame({"a": ["x", "y"]}))
    assert matrix.columns == []
    assert matrix.pairs == []


def test_single_numeric_column_returns_empty_matrix():
    matrix = correlations(pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]}))
    assert matrix.pairs == []


def test_all_null_column_does_not_crash_profiling():
    profile = profile_dataset(pd.DataFrame({"a": [None, None], "b": [1, 2]}))
    empty = next(c for c in profile.columns if c.name == "a")
    assert empty.non_null_count == 0
    assert empty.null_pct == 100.0


def test_empty_dataframe_does_not_crash():
    profile = profile_dataset(pd.DataFrame({"a": []}))
    assert profile.row_count == 0


def test_infer_semantic_type_on_empty_series():
    assert infer_semantic_type(pd.Series([], dtype=object)) == "text"


def test_high_cardinality_strings_are_text_not_categorical():
    series = pd.Series([f"note-{i}" for i in range(200)])
    assert infer_semantic_type(series) == "text"

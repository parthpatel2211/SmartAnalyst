import pandas as pd

from backend_app.charts import resolve_chart
from backend_app.engine import QueryResult


def _result(df: pd.DataFrame) -> QueryResult:
    return QueryResult(
        sql="SELECT 1",
        columns=list(df.columns),
        rows=df.to_dict(orient="records"),
        row_count=len(df),
        truncated=False,
    )


def test_accepts_a_valid_proposed_spec():
    result = _result(pd.DataFrame({"region": ["N", "S"], "total": [1, 2]}))
    spec = resolve_chart({"kind": "bar", "x": "region", "y": ["total"], "title": "T"}, result)
    assert spec.kind == "bar"
    assert spec.x == "region"
    assert spec.y == ["total"]
    assert spec.title == "T"


def test_rejects_spec_referencing_a_missing_column():
    result = _result(pd.DataFrame({"region": ["N"], "total": [1]}))
    spec = resolve_chart({"kind": "bar", "x": "nope", "y": ["total"], "title": "T"}, result)
    assert spec.x == "region", "should fall back rather than emit a broken chart"


def test_rejects_spec_with_a_missing_y_column():
    result = _result(pd.DataFrame({"region": ["N"], "total": [1]}))
    spec = resolve_chart({"kind": "bar", "x": "region", "y": ["ghost"], "title": "T"}, result)
    assert spec.y != ["ghost"]


def test_rejects_unknown_chart_kind():
    result = _result(pd.DataFrame({"region": ["N"], "total": [1]}))
    spec = resolve_chart({"kind": "pie", "x": "region", "y": ["total"], "title": "T"}, result)
    assert spec.kind != "pie", "pie is never produced"


def test_accepts_a_string_y_by_coercing_it_to_a_list():
    result = _result(pd.DataFrame({"region": ["N", "S"], "total": [1, 2]}))
    spec = resolve_chart({"kind": "bar", "x": "region", "y": "total", "title": "T"}, result)
    assert spec.y == ["total"]


def test_drops_an_invalid_series_without_discarding_the_whole_spec():
    result = _result(pd.DataFrame({"region": ["N", "S"], "total": [1, 2]}))
    spec = resolve_chart(
        {"kind": "bar", "x": "region", "y": ["total"], "series": "ghost", "title": "T"}, result
    )
    assert spec.kind == "bar"
    assert spec.series is None


def test_fallback_datetime_and_numeric_gives_line():
    df = pd.DataFrame({"d": pd.date_range("2024-01-01", periods=5), "v": range(5)})
    assert resolve_chart(None, _result(df)).kind == "line"


def test_fallback_categorical_and_numeric_gives_bar():
    df = pd.DataFrame({"c": ["a", "b", "c"], "v": [1, 2, 3]})
    assert resolve_chart(None, _result(df)).kind == "bar"


def test_fallback_two_numerics_gives_scatter():
    df = pd.DataFrame({"x": [1.5, 2.5, 3.5, 4.5], "y": [4.5, 5.5, 6.5, 7.5]})
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


def test_table_spec_is_accepted_without_axis_columns():
    result = _result(pd.DataFrame({"a": [1], "b": [2]}))
    spec = resolve_chart({"kind": "table", "title": "Rows"}, result)
    assert spec.kind == "table"
    assert spec.title == "Rows"


def test_identifier_column_is_not_histogrammed():
    """A histogram of order numbers describes the numbering, not the data."""
    df = pd.DataFrame({"order_id": range(1, 101)})
    assert resolve_chart(None, _result(df)).kind == "table"


def test_identifier_is_not_used_as_a_measure_against_a_category():
    df = pd.DataFrame({"region": [f"r{i}" for i in range(30)], "order_id": range(30)})
    spec = resolve_chart(None, _result(df))
    assert spec.y != ["order_id"]


def test_unique_aggregate_counts_are_still_charted():
    """A GROUP BY returning distinct integer counts is measures, not IDs.

    The identifier heuristic keys on near-total distinctness, which every
    small aggregate result trivially satisfies. It must not fire here.
    """
    df = pd.DataFrame({"region": ["N", "S", "E"], "orders": [7, 12, 19]})
    spec = resolve_chart(None, _result(df))
    assert spec.kind == "bar"
    assert spec.y == ["orders"]


# --------------------------------------------------------------------------
# Defects seen in real output
# --------------------------------------------------------------------------


def test_measures_of_incomparable_scale_do_not_share_an_axis():
    """Seen live: Total_Orders and Total_Revenue plotted together, which
    flattened the order counts onto the baseline where they could not be read.
    Two scales need two charts, never a second y-axis."""
    df = pd.DataFrame(
        {
            "region": ["N", "S", "E", "W"],
            "total_orders": [1200, 1300, 1100, 1400],
            "total_revenue": [2_400_000, 2_500_000, 2_300_000, 2_610_000],
        }
    )
    spec = resolve_chart(
        {
            "kind": "bar",
            "x": "region",
            "y": ["total_orders", "total_revenue"],
            "title": "T",
        },
        _result(df),
    )
    assert len(spec.y) == 1
    assert spec.y == ["total_revenue"], "the larger measure survives"


def test_measures_of_similar_scale_may_share_an_axis():
    df = pd.DataFrame(
        {"region": ["N", "S"], "revenue": [2_400_000, 2_500_000], "cost": [1_500_000, 1_600_000]}
    )
    spec = resolve_chart(
        {"kind": "bar", "x": "region", "y": ["revenue", "cost"], "title": "T"}, _result(df)
    )
    assert set(spec.y) == {"revenue", "cost"}


def test_a_second_categorical_dimension_becomes_the_series():
    """Seen live: a region-by-category comparison drew 16 bars labelled
    East East East East North North..., because category was dropped."""
    rows = []
    for region in ["East", "North", "South", "West"]:
        for category in ["Apparel", "Footwear", "Accessories", "Outerwear"]:
            rows.append({"region": region, "category": category, "revenue": 100})
    spec = resolve_chart(
        {"kind": "bar", "x": "region", "y": ["revenue"], "title": "T"},
        _result(pd.DataFrame(rows)),
    )
    assert spec.series == "category"
    assert spec.y == ["revenue"]


def test_a_grouped_chart_plots_one_measure_only():
    """Colour is already spent on the series; a second measure is unreadable."""
    rows = []
    for region in ["East", "West"]:
        for channel in ["Online", "Retail"]:
            rows.append({"region": region, "channel": channel, "revenue": 100, "cost": 60})
    spec = resolve_chart(
        {"kind": "bar", "x": "region", "y": ["revenue", "cost"], "series": "channel", "title": "T"},
        _result(pd.DataFrame(rows)),
    )
    assert len(spec.y) == 1


def test_a_single_categorical_dimension_gets_no_series():
    df = pd.DataFrame({"region": ["N", "S"], "revenue": [1, 2]})
    spec = resolve_chart(
        {"kind": "bar", "x": "region", "y": ["revenue"], "title": "T"}, _result(df)
    )
    assert spec.series is None


def test_fallback_also_groups_by_a_second_categorical():
    rows = []
    for region in ["East", "West"]:
        for category in ["A", "B"]:
            rows.append({"region": region, "category": category, "revenue": 10})
    spec = resolve_chart(None, _result(pd.DataFrame(rows)))
    assert spec.kind == "bar"
    assert spec.series == "category"


def test_scatter_is_left_alone_by_the_scale_guard():
    """Scatter's two axes are independent, so differing magnitudes are fine."""
    df = pd.DataFrame({"orders": [1, 2, 3, 4], "revenue": [1e6, 2e6, 3e6, 4e6]})
    spec = resolve_chart(
        {"kind": "scatter", "x": "orders", "y": ["revenue"], "title": "T"}, _result(df)
    )
    assert spec.kind == "scatter"
    assert spec.y == ["revenue"]


def test_fallback_never_returns_a_chart_referencing_absent_columns():
    """Whatever the fallback picks must be renderable against the result."""
    frames = [
        pd.DataFrame({"d": pd.date_range("2024-01-01", periods=5), "v": range(5)}),
        pd.DataFrame({"c": ["a", "b"], "v": [1, 2]}),
        pd.DataFrame({"x": [1.5, 2.5], "y": [3.5, 4.5]}),
        pd.DataFrame({"v": [1.0, 2.0, 3.0]}),
        pd.DataFrame({"n": [42]}),
    ]
    for frame in frames:
        result = _result(frame)
        spec = resolve_chart(None, result)
        if spec.x is not None:
            assert spec.x in result.columns
        for column in spec.y:
            assert column in result.columns

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


def test_severe_nulls_rank_higher_than_mild_ones():
    severe = _insights_for(pd.DataFrame({"a": [None] * 80 + [1] * 20, "b": [1] * 100}))
    mild = _insights_for(pd.DataFrame({"a": [None] * 25 + [1] * 75, "b": [1] * 100}))
    assert next(i for i in severe if i.kind == "high_nulls").severity == "high"
    assert next(i for i in mild if i.kind == "high_nulls").severity == "medium"


def test_detects_constant_column():
    df = pd.DataFrame({"a": range(50), "flag": ["yes"] * 50})
    assert "constant_column" in _kinds(_insights_for(df))


def test_detects_skewed_distribution():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"v": rng.gamma(1.2, 50.0, 500), "w": rng.normal(0, 1, 500)})
    skewed = [i for i in _insights_for(df) if i.kind == "skewed"]
    assert any("v" in i.columns for i in skewed)


def test_does_not_flag_a_normal_distribution_as_skewed():
    rng = np.random.default_rng(7)
    df = pd.DataFrame({"v": rng.normal(0, 1, 1000), "w": rng.normal(5, 2, 1000)})
    assert not [i for i in _insights_for(df) if "v" in i.columns and i.kind == "skewed"]


def test_detects_duplicate_rows():
    df = pd.concat([pd.DataFrame({"a": [1, 2, 3]})] * 2, ignore_index=True)
    assert "duplicate_rows" in _kinds(_insights_for(df))


def test_detects_outlier_heavy_column():
    values = list(np.zeros(100)) + [1000.0] * 12
    df = pd.DataFrame({"v": values})
    assert "outliers" in _kinds(_insights_for(df))


def test_clean_dataset_produces_no_warnings():
    rng = np.random.default_rng(2)
    df = pd.DataFrame(
        {
            "a": rng.normal(0, 1, 300),
            "b": rng.normal(5, 2, 300),
            "c": rng.choice(["x", "y", "z"], 300),
        }
    )
    kinds = _kinds(_insights_for(df))
    assert "high_nulls" not in kinds
    assert "constant_column" not in kinds
    assert "duplicate_rows" not in kinds


def test_insights_are_sorted_by_severity():
    df = pd.DataFrame({"a": [None] * 90 + [1] * 10, "b": ["k"] * 100})
    severities = [i.severity for i in _insights_for(df)]
    order = {"high": 0, "medium": 1, "low": 2}
    assert severities == sorted(severities, key=lambda s: order[s])


def test_every_insight_has_a_title_and_detail():
    df = pd.DataFrame({"a": [None] * 60 + [1] * 40, "b": ["k"] * 100})
    for insight in _insights_for(df):
        assert insight.title.strip()
        assert insight.detail.strip()
        assert insight.severity in {"high", "medium", "low"}


def test_empty_dataframe_produces_no_insights_and_does_not_crash():
    assert _insights_for(pd.DataFrame({"a": []})) == []

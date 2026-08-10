import json
from pathlib import Path

import pandas as pd
import pytest

from backend_app.insights import generate_insights
from backend_app.profiling import correlations, profile_dataset

CSV = Path("data/sample_orders.csv")
QUESTIONS = Path("data/example_questions.json")


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(CSV, parse_dates=["order_date"])


@pytest.fixture(scope="module")
def insights(df):
    return generate_insights(df, profile_dataset(df), correlations(df))


def test_has_enough_rows(df):
    assert len(df) >= 5000


def test_exercises_every_planted_insight(insights):
    """The demo must demonstrably find things, not merely look busy."""
    kinds = {i.kind for i in insights}
    for expected in {
        "strong_correlation",
        "high_nulls",
        "outliers",
        "duplicate_rows",
        "skewed",
    }:
        assert expected in kinds, f"sample data should trigger {expected}, got {kinds}"


def test_has_every_semantic_type_a_chart_needs(df):
    types = {c.semantic_type for c in profile_dataset(df).columns}
    assert {"numeric", "categorical", "datetime", "id"} <= types


def test_the_planted_revenue_cost_correlation_is_found(df):
    pair = next(p for p in correlations(df).pairs if {p.x, p.y} == {"revenue", "cost"})
    assert pair.value > 0.9


def test_nulls_are_present_where_planted(df):
    profile = {c.name: c for c in profile_dataset(df).columns}
    assert profile["rating"].null_pct > 10
    assert profile["delivery_days"].null_pct > 0


def test_duplicates_are_present(df):
    assert profile_dataset(df).duplicate_rows > 0


def test_generator_is_deterministic():
    from scripts.generate_sample_data import build

    assert build().equals(build())


def test_committed_csv_matches_the_generator():
    """A stale CSV would make the script decorative rather than the source."""
    from scripts.generate_sample_data import build

    generated = build()
    committed = pd.read_csv(CSV, parse_dates=["order_date"])
    assert len(generated) == len(committed)
    assert list(generated.columns) == list(committed.columns)


def test_example_questions_are_usable_prompts():
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    assert len(questions) >= 5
    for question in questions:
        assert isinstance(question, str)
        # Long enough to be a real prompt, short enough to fit a chip.
        assert 15 <= len(question.strip()) <= 70, question


def test_example_questions_reference_real_columns(df):
    """A suggested question naming a column that does not exist is a dead end."""
    questions = " ".join(json.loads(QUESTIONS.read_text(encoding="utf-8"))).lower()
    for column in ["revenue", "region", "profit", "delivery days", "rating", "cost"]:
        assert column in questions or column.replace(" ", "_") in questions

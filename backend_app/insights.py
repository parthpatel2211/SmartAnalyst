"""Deterministic findings.

Each generator is a pure function over the dataframe and its profile. No
language model is involved anywhere in this module, which is the point:
these are the observations an analyst would make, computed rather than
guessed, so they are reproducible, instant, and free — and they work with
no API key.
"""

import pandas as pd

from backend_app.models import CorrelationMatrix, DatasetProfile, Insight

CORRELATION_THRESHOLD = 0.7

HIGH_NULL_PCT = 20.0
CRITICAL_NULL_PCT = 50.0

SKEW_THRESHOLD = 1.0
OUTLIER_PCT_THRESHOLD = 5.0

#: Findings of the same kind are capped at the strongest few. A wide table of
#: related measures will trip the same rule in every column -- six columns
#: reported as right-skewed is one observation printed six times, and a panel
#: of near-duplicates reads as noise rather than analysis.
MAX_PER_KIND = 3

HIGH_CARDINALITY_RATIO = 0.5
HIGH_CARDINALITY_MIN_DISTINCT = 20

DUPLICATE_PCT_HIGH = 5.0

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _strong_correlations(corr: CorrelationMatrix) -> list[Insight]:
    found = []
    for pair in corr.pairs[:MAX_PER_KIND]:
        if abs(pair.value) < CORRELATION_THRESHOLD:
            break  # pairs are ranked, so nothing after this qualifies either
        direction = "positively" if pair.value > 0 else "negatively"
        found.append(
            Insight(
                kind="strong_correlation",
                severity="medium",
                title=f"{pair.x} and {pair.y} are strongly {direction} correlated",
                detail=(
                    f"Pearson r = {pair.value:.2f}. One column may be derived from "
                    "the other, which would make them redundant in a model."
                ),
                columns=[pair.x, pair.y],
            )
        )
    return found


def _high_null_columns(profile: DatasetProfile) -> list[Insight]:
    found = []
    for column in profile.columns:
        if column.null_pct < HIGH_NULL_PCT:
            continue
        critical = column.null_pct >= CRITICAL_NULL_PCT
        found.append(
            Insight(
                kind="high_nulls",
                severity="high" if critical else "medium",
                title=f"{column.name} is {column.null_pct:.0f}% missing",
                detail=(
                    "More than half the values are absent, so any aggregate over "
                    "this column describes a minority of the data."
                    if critical
                    else "Decide whether these rows should be imputed or excluded."
                ),
                columns=[column.name],
            )
        )
    return found


def _constant_columns(profile: DatasetProfile) -> list[Insight]:
    return [
        Insight(
            kind="constant_column",
            severity="low",
            title=f"{column.name} holds a single value throughout",
            detail="A constant column carries no information and can be dropped.",
            columns=[column.name],
        )
        for column in profile.columns
        if column.distinct_count <= 1 and profile.row_count > 1
    ]


def _skewed_columns(profile: DatasetProfile) -> list[Insight]:
    candidates = [
        column
        for column in profile.columns
        if column.semantic_type == "numeric"
        and column.skew is not None
        and abs(column.skew) >= SKEW_THRESHOLD
    ]
    candidates.sort(key=lambda column: abs(column.skew or 0), reverse=True)

    found = []
    for column in candidates[:MAX_PER_KIND]:
        side = "right" if (column.skew or 0) > 0 else "left"
        found.append(
            Insight(
                kind="skewed",
                severity="low",
                title=f"{column.name} is {side}-skewed",
                detail=(
                    f"Skew = {column.skew:.2f}, which pulls the mean "
                    f"({column.mean:,.2f}) away from the median "
                    f"({column.median:,.2f}). Prefer the median here."
                ),
                columns=[column.name],
            )
        )
    return found


def _outlier_heavy_columns(profile: DatasetProfile) -> list[Insight]:
    candidates = [
        (column, column.outlier_count / column.non_null_count * 100)
        for column in profile.columns
        if column.outlier_count is not None and column.non_null_count > 0
    ]
    candidates = [(c, pct) for c, pct in candidates if pct >= OUTLIER_PCT_THRESHOLD]
    candidates.sort(key=lambda item: item[1], reverse=True)

    return [
        Insight(
            kind="outliers",
            severity="medium",
            title=f"{column.name} has {column.outlier_count} outliers ({pct:.0f}%)",
            detail=(
                "Values fall more than 1.5 x IQR beyond the quartiles. Worth "
                "checking for data-entry errors before averaging."
            ),
            columns=[column.name],
        )
        for column, pct in candidates[:MAX_PER_KIND]
    ]


def _duplicate_rows(profile: DatasetProfile) -> list[Insight]:
    if profile.duplicate_rows == 0:
        return []
    pct = profile.duplicate_rows / max(profile.row_count, 1) * 100
    return [
        Insight(
            kind="duplicate_rows",
            severity="high" if pct >= DUPLICATE_PCT_HIGH else "medium",
            title=f"{profile.duplicate_rows} duplicate rows ({pct:.1f}%)",
            detail="Identical rows double-count in every aggregation over this table.",
        )
    ]


def _high_cardinality_columns(profile: DatasetProfile) -> list[Insight]:
    return [
        Insight(
            kind="high_cardinality",
            severity="low",
            title=f"{column.name} has {column.distinct_count} distinct values",
            detail="Too many categories to chart directly; group or filter first.",
            columns=[column.name],
        )
        for column in profile.columns
        if column.semantic_type in {"categorical", "text"}
        and column.cardinality_ratio >= HIGH_CARDINALITY_RATIO
        and column.distinct_count > HIGH_CARDINALITY_MIN_DISTINCT
    ]


def generate_insights(
    df: pd.DataFrame, profile: DatasetProfile, corr: CorrelationMatrix
) -> list[Insight]:
    """Run every generator and rank the results by severity."""
    if profile.row_count == 0:
        return []

    insights = [
        *_duplicate_rows(profile),
        *_high_null_columns(profile),
        *_strong_correlations(corr),
        *_outlier_heavy_columns(profile),
        *_skewed_columns(profile),
        *_constant_columns(profile),
        *_high_cardinality_columns(profile),
    ]
    insights.sort(key=lambda insight: _SEVERITY_ORDER[insight.severity])
    return insights

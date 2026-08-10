"""Deterministic dataset profiling.

Everything here is computed in pandas. No language model is involved, which
means the numbers are reproducible, instant, free, and correct — and it is
why profiling works with no API key.
"""

import numpy as np
import pandas as pd

from backend_app.models import (
    ColumnProfile,
    ColumnSchema,
    CorrelationMatrix,
    CorrelationPair,
    DatasetProfile,
    TopValue,
)

#: Above this share of distinct integer values, a numeric column is an
#: identifier rather than a measure.
ID_CARDINALITY_THRESHOLD = 0.95

#: Below this many values, near-total distinctness carries no information:
#: three sales figures that happen to differ are three sales figures, not
#: three identifiers. Without this floor, every small CSV and every GROUP BY
#: result has its measures misread as keys, which strips them out of the
#: correlations and tells the model not to aggregate them.
MIN_ROWS_FOR_ID_INFERENCE = 20

#: Above this many distinct strings, a column is free text rather than a
#: category worth charting.
CATEGORICAL_MAX_DISTINCT = 50

TOP_VALUE_LIMIT = 5
IQR_MULTIPLIER = 1.5


def infer_semantic_type(series: pd.Series) -> str:
    """Classify a column beyond its storage dtype.

    The dtype says ``int64``; an analyst needs to know whether that is an
    order number or an amount, because the two get aggregated and charted
    completely differently. Summing a column of IDs produces a number, just
    not a meaningful one.
    """
    non_null = series.dropna()
    if non_null.empty:
        return "text"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        ratio = non_null.nunique() / len(non_null)
        nearly_unique_integers = (
            len(non_null) >= MIN_ROWS_FOR_ID_INFERENCE
            and ratio >= ID_CARDINALITY_THRESHOLD
            and pd.api.types.is_integer_dtype(series)
        )
        return "id" if nearly_unique_integers else "numeric"
    if non_null.nunique() <= CATEGORICAL_MAX_DISTINCT:
        return "categorical"
    return "text"


def build_schema(df: pd.DataFrame) -> list[ColumnSchema]:
    """The compact column description sent to the model when writing SQL."""
    total = max(len(df), 1)
    return [
        ColumnSchema(
            name=str(column),
            dtype=str(df[column].dtype),
            semantic_type=infer_semantic_type(df[column]),
            null_pct=round(float(df[column].isna().sum()) / total * 100, 2),
            distinct_count=int(df[column].nunique(dropna=True)),
        )
        for column in df.columns
    ]


def _numeric_stats(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if values.empty:
        return {}

    q1, median, q3 = (float(values.quantile(q)) for q in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    lower, upper = q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr
    outliers = int(((values < lower) | (values > upper)).sum())

    return {
        "min": float(values.min()),
        "q1": q1,
        "median": median,
        "mean": float(values.mean()),
        "q3": q3,
        "max": float(values.max()),
        "std": float(values.std()) if len(values) > 1 else 0.0,
        "skew": float(values.skew()) if len(values) > 2 else 0.0,
        "outlier_count": outliers,
    }


def _datetime_span(series: pd.Series) -> dict:
    """The period a date column covers, which is a headline fact about a
    dataset and cannot be read off the numeric statistics."""
    values = series.dropna()
    if values.empty:
        return {}
    return {
        "min_label": pd.Timestamp(values.min()).date().isoformat(),
        "max_label": pd.Timestamp(values.max()).date().isoformat(),
    }


def _top_values(series: pd.Series) -> list[TopValue]:
    counts = series.dropna().value_counts().head(TOP_VALUE_LIMIT)
    return [TopValue(value=str(index), count=int(count)) for index, count in counts.items()]


def profile_dataset(df: pd.DataFrame) -> DatasetProfile:
    """Full per-column statistics plus dataset-level shape."""
    total = max(len(df), 1)
    columns: list[ColumnProfile] = []

    for column in df.columns:
        series = df[column]
        semantic = infer_semantic_type(series)
        non_null = int(series.notna().sum())
        distinct = int(series.nunique(dropna=True))

        stats: dict = {}
        if semantic in {"numeric", "id"}:
            stats = _numeric_stats(series)
        elif semantic == "datetime":
            stats = _datetime_span(series)

        top = _top_values(series) if semantic in {"categorical", "boolean", "text"} else []

        columns.append(
            ColumnProfile(
                name=str(column),
                dtype=str(series.dtype),
                semantic_type=semantic,
                non_null_count=non_null,
                null_pct=round((len(df) - non_null) / total * 100, 2),
                distinct_count=distinct,
                cardinality_ratio=round(distinct / total, 4),
                top_values=top,
                **stats,
            )
        )

    return DatasetProfile(
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_rows=int(df.duplicated().sum()),
        memory_bytes=int(df.memory_usage(deep=True).sum()),
        columns=columns,
    )


def correlations(df: pd.DataFrame) -> CorrelationMatrix:
    """Pearson correlation across genuine measures.

    Identifier columns are excluded: a sequential order number correlates
    with anything that trends over time, which is an artefact of row order
    rather than a relationship in the data.
    """
    measures = [
        column
        for column in df.select_dtypes(include=[np.number]).columns
        if infer_semantic_type(df[column]) == "numeric"
    ]

    if len(measures) < 2:
        return CorrelationMatrix(columns=[], matrix=[], pairs=[])

    corr = df[measures].corr(method="pearson")
    names = [str(column) for column in corr.columns]

    matrix = [
        [None if pd.isna(value) else round(float(value), 4) for value in row]
        for row in corr.to_numpy()
    ]

    pairs = [
        CorrelationPair(x=names[i], y=names[j], value=round(float(corr.iat[i, j]), 4))
        for i in range(len(names))
        for j in range(i + 1, len(names))
        if not pd.isna(corr.iat[i, j])
    ]
    pairs.sort(key=lambda pair: abs(pair.value), reverse=True)

    return CorrelationMatrix(columns=names, matrix=matrix, pairs=pairs)

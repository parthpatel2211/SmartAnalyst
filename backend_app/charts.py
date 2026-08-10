"""Chart selection.

The model proposes a chart; this module verifies it against the columns the
query actually returned. A confidently wrong chart is worse than a plain
table, so anything unverifiable falls back to a heuristic driven by the
shape of the result.

No pie or donut charts are ever produced. Quantity encoded as angle is read
less accurately than quantity encoded as length or position.
"""

import pandas as pd

from backend_app.engine import QueryResult
from backend_app.models import ChartSpec
from backend_app.profiling import infer_semantic_type

VALID_KINDS = {"bar", "line", "area", "scatter", "histogram", "table"}

#: Beyond this many bars the axis becomes unreadable and a table serves better.
MAX_BAR_CATEGORIES = 25

#: How many measures to plot on one chart before it becomes noise.
MAX_SERIES = 3

def _classify_columns(result: QueryResult) -> dict[str, list[str]]:
    """Sort result columns into the roles a chart can use.

    Identifiers get their own bucket and are never plotted as measures:
    histogramming a column of order numbers pictures the numbering scheme
    rather than the data. The row-count floor that stops small aggregate
    results being misread as identifiers lives in
    :func:`profiling.infer_semantic_type`, so it is not repeated here.
    """
    frame = pd.DataFrame(result.rows, columns=result.columns)
    buckets: dict[str, list[str]] = {
        "numeric": [],
        "datetime": [],
        "categorical": [],
        "id": [],
    }

    if frame.empty:
        return buckets

    for column in result.columns:
        # Values arrive from JSON-shaped dicts, so re-infer rather than trusting dtype.
        series = frame[column].infer_objects()
        semantic = infer_semantic_type(series)

        if semantic in buckets:
            buckets[semantic].append(column)
        elif semantic == "boolean":
            buckets["categorical"].append(column)

    return buckets


def fallback_chart(result: QueryResult) -> ChartSpec:
    """Pick a chart from the shape of the result alone."""
    if result.row_count == 0 or not result.columns:
        return ChartSpec(kind="table", title="Result")

    buckets = _classify_columns(result)
    numeric = buckets["numeric"]
    datetimes = buckets["datetime"]
    categorical = buckets["categorical"]

    if datetimes and numeric:
        return ChartSpec(
            kind="line", x=datetimes[0], y=numeric[:MAX_SERIES], title="Trend over time"
        )

    if categorical and numeric and result.row_count <= MAX_BAR_CATEGORIES:
        return ChartSpec(
            kind="bar",
            x=categorical[0],
            y=numeric[:MAX_SERIES],
            title="Comparison by category",
        )

    if len(numeric) >= 2 and not categorical:
        return ChartSpec(kind="scatter", x=numeric[0], y=[numeric[1]], title="Relationship")

    if len(numeric) == 1 and not categorical and result.row_count > 1:
        return ChartSpec(kind="histogram", x=numeric[0], y=[], title="Distribution")

    return ChartSpec(kind="table", title="Result")


def resolve_chart(proposed: dict | None, result: QueryResult) -> ChartSpec:
    """Validate the model's chart against the real result, or fall back."""
    if not proposed:
        return fallback_chart(result)

    kind = str(proposed.get("kind", "")).lower()
    if kind not in VALID_KINDS:
        return fallback_chart(result)

    title = str(proposed.get("title") or "Result")

    if kind == "table":
        return ChartSpec(kind="table", title=title)

    available = set(result.columns)

    x = proposed.get("x")
    if x is not None and x not in available:
        return fallback_chart(result)

    y = proposed.get("y") or []
    if isinstance(y, str):
        y = [y]
    if not isinstance(y, list) or any(column not in available for column in y):
        return fallback_chart(result)
    if kind != "histogram" and not y:
        return fallback_chart(result)

    # A bad grouping column is not worth discarding an otherwise valid chart for.
    series = proposed.get("series")
    if series is not None and series not in available:
        series = None

    return ChartSpec(kind=kind, x=x, y=list(y), series=series, title=title)

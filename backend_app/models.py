"""Pydantic schemas shared across routers.

These are the API contract. The frontend's ``types.ts`` mirrors this file
field for field, so a rename here is a breaking change there.
"""

from pydantic import BaseModel

# --------------------------------------------------------------------------
# Schema and session
# --------------------------------------------------------------------------


class ColumnSchema(BaseModel):
    """A column as the model sees it when writing SQL."""

    name: str
    dtype: str
    #: id | categorical | numeric | datetime | boolean | text
    semantic_type: str
    null_pct: float
    distinct_count: int


class QATurn(BaseModel):
    """One exchange, kept so follow-up questions can resolve references."""

    question: str
    sql: str
    summary: str


# --------------------------------------------------------------------------
# Profiling
# --------------------------------------------------------------------------


class TopValue(BaseModel):
    value: str
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic_type: str
    non_null_count: int
    null_pct: float
    distinct_count: int
    cardinality_ratio: float
    top_values: list[TopValue] = []

    # Numeric columns only; None elsewhere.
    min: float | None = None
    q1: float | None = None
    median: float | None = None
    mean: float | None = None
    q3: float | None = None
    max: float | None = None
    std: float | None = None
    skew: float | None = None
    outlier_count: int | None = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    memory_bytes: int
    columns: list[ColumnProfile]


class CorrelationPair(BaseModel):
    x: str
    y: str
    value: float


class CorrelationMatrix(BaseModel):
    columns: list[str]
    matrix: list[list[float | None]]
    #: Unique pairs ranked by absolute correlation, strongest first.
    pairs: list[CorrelationPair]

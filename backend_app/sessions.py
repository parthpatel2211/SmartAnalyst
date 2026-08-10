"""Per-upload session state.

Replaces the module-level ``uploaded_df`` global of the original prototype,
under which every caller shared a single dataframe: whoever uploaded last
silently replaced everyone else's data.

Storage is a process-local dict, which means the server runs single-worker.
That is a deliberate trade-off for a free-tier deployment and is documented
in the README rather than hidden. Multi-worker operation would need an
external store.
"""

import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import duckdb
import pandas as pd

from backend_app.engine import create_connection
from backend_app.models import ColumnSchema, QATurn
from backend_app.profiling import build_schema

#: How many prior exchanges are replayed to the model for follow-up questions.
MAX_HISTORY_TURNS = 3

_BYTES_PER_MB = 1_048_576

#: Share of values that must parse as dates before a text column is converted.
_DATETIME_PARSE_THRESHOLD = 0.9
_DATETIME_SAMPLE_SIZE = 200


class SessionNotFound(KeyError):
    """The requested session does not exist or has expired."""


class UploadTooLarge(ValueError):
    """The upload exceeded a configured byte or row limit, or held no data."""


def read_csv_limited(raw: bytes, *, max_bytes: int, max_rows: int) -> pd.DataFrame:
    """Parse CSV bytes, refusing anything past the configured bounds.

    The byte check runs before parsing so an oversized file is rejected
    without being materialized.
    """
    if len(raw) > max_bytes:
        raise UploadTooLarge(
            f"That file is {len(raw) / _BYTES_PER_MB:.1f} MB; the limit is "
            f"{max_bytes / _BYTES_PER_MB:.0f} MB."
        )

    # One row past the limit distinguishes "exactly at the limit" from "over".
    try:
        frame = pd.read_csv(io.BytesIO(raw), nrows=max_rows + 1)
    except pd.errors.EmptyDataError as err:
        # A zero-byte or header-less file fails in the parser before the
        # emptiness check below can run.
        raise UploadTooLarge("That file contains no data rows.") from err

    if len(frame) > max_rows:
        raise UploadTooLarge(f"That file has more than {max_rows:,} rows.")
    if frame.empty or frame.columns.empty:
        raise UploadTooLarge("That file contains no data rows.")

    return coerce_datetime_columns(frame)


def _looks_like_datetime(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(_DATETIME_SAMPLE_SIZE)
    if sample.empty:
        return False

    # A column of bare numbers is not a date. Without this guard a year column,
    # a postcode, or an ID would all be silently converted.
    if sample.str.fullmatch(r"[-+]?\d*\.?\d+").all():
        return False

    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() >= _DATETIME_PARSE_THRESHOLD)


def coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Parse date-like text columns into real datetimes.

    read_csv leaves dates as strings, which has consequences well past
    cosmetics: DuckDB receives VARCHAR so DATE_TRUNC and date arithmetic fail,
    the chart heuristic never sees a time axis so trends render as bars or
    tables, and the model is told the column is free text. A dataset of orders
    loses its most useful dimension.
    """
    converted = df.copy()
    for column in converted.columns:
        series = converted[column]
        if not pd.api.types.is_object_dtype(series):
            continue
        if not _looks_like_datetime(series):
            continue
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
        # Only commit if the full column parses as well as the sample did.
        if parsed.notna().mean() >= _DATETIME_PARSE_THRESHOLD:
            converted[column] = parsed
    return converted


@dataclass
class DatasetSession:
    """One uploaded dataset and the conversation held about it."""

    id: str
    name: str
    df: pd.DataFrame
    conn: duckdb.DuckDBPyConnection
    schema: list[ColumnSchema]
    created_at: datetime
    last_used_at: datetime
    history: list[QATurn] = field(default_factory=list)

    def add_turn(self, *, question: str, sql: str, summary: str) -> None:
        """Record an exchange, keeping only the most recent few."""
        self.history.append(QATurn(question=question, sql=sql, summary=summary))
        del self.history[:-MAX_HISTORY_TURNS]

    def touch(self) -> None:
        self.last_used_at = datetime.now(UTC)


class SessionStore:
    """TTL- and capacity-bounded session storage."""

    def __init__(self, *, ttl_seconds: int, max_sessions: int) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max = max_sessions
        self._sessions: dict[str, DatasetSession] = {}

    def __len__(self) -> int:
        return len(self._sessions)

    def create(self, df: pd.DataFrame, *, name: str) -> DatasetSession:
        self.evict_expired()
        now = datetime.now(UTC)
        session = DatasetSession(
            id=str(uuid.uuid4()),
            name=name,
            df=df,
            conn=create_connection(df),
            schema=build_schema(df),
            created_at=now,
            last_used_at=now,
        )
        self._sessions[session.id] = session
        self._enforce_cap()
        return session

    def get(self, session_id: str) -> DatasetSession:
        self.evict_expired()
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(
                "That dataset has expired or was never uploaded. Upload the file again."
            )
        session.touch()
        return session

    def evict_expired(self) -> None:
        cutoff = datetime.now(UTC) - self._ttl
        expired = [s.id for s in self._sessions.values() if s.last_used_at < cutoff]
        for session_id in expired:
            self._close(session_id)

    def _enforce_cap(self) -> None:
        while len(self._sessions) > self._max:
            oldest = min(self._sessions.values(), key=lambda s: s.last_used_at)
            self._close(oldest.id)

    def _close(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.conn.close()

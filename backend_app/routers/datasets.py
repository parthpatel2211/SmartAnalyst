"""Upload and deterministic analysis.

Every route here works without an API key. That is deliberate: a first-time
visitor should see real analysis of real data before being asked for
anything.
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile

from backend_app.config import get_settings
from backend_app.deps import get_store, session_or_404
from backend_app.insights import generate_insights
from backend_app.models import (
    CorrelationMatrix,
    DatasetProfile,
    InsightsResponse,
    UploadResponse,
)
from backend_app.profiling import correlations, profile_dataset
from backend_app.sessions import UploadTooLarge, read_csv_limited

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", status_code=201, response_model=UploadResponse)
async def upload_dataset(file: UploadFile) -> UploadResponse:
    """Load a CSV into a new session and return its schema."""
    settings = get_settings()
    raw = await file.read()

    try:
        frame = read_csv_limited(
            raw, max_bytes=settings.max_upload_bytes, max_rows=settings.max_rows
        )
    except UploadTooLarge as err:
        raise HTTPException(status_code=413, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=400, detail=f"That file could not be read as CSV: {err}"
        ) from err

    session = get_store().create(frame, name=file.filename or "dataset.csv")
    logger.info("Created session %s with shape %s", session.id, frame.shape)

    return UploadResponse(
        session_id=session.id,
        name=session.name,
        row_count=len(frame),
        column_count=len(frame.columns),
        columns=session.schema,
    )


@router.get("/{session_id}/profile", response_model=DatasetProfile)
async def get_profile(session_id: str) -> DatasetProfile:
    return profile_dataset(session_or_404(session_id).df)


@router.get("/{session_id}/insights", response_model=InsightsResponse)
async def get_insights(session_id: str) -> InsightsResponse:
    df = session_or_404(session_id).df
    profile = profile_dataset(df)
    return InsightsResponse(insights=generate_insights(df, profile, correlations(df)))


@router.get("/{session_id}/correlations", response_model=CorrelationMatrix)
async def get_correlations(session_id: str) -> CorrelationMatrix:
    return correlations(session_or_404(session_id).df)

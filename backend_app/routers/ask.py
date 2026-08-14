"""The question-answering pipeline.

Question -> model -> SQL -> guard -> DuckDB -> rows plus a validated chart.
The guard sits between the model and the database, which is the only reason
it is safe to run a query a language model wrote.
"""

import logging

import duckdb
from fastapi import APIRouter, Header, HTTPException

from backend_app.charts import resolve_chart
from backend_app.config import get_settings
from backend_app.deps import session_or_404
from backend_app.engine import run_query
from backend_app.llm import LlmError, ask_model, build_prompt, narrate, parse_response
from backend_app.models import AskRequest, AskResponse
from backend_app.sql_guard import SqlValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["ask"])

SAMPLE_ROWS = 3


@router.post("/{session_id}/ask", response_model=AskResponse)
async def ask(
    session_id: str,
    payload: AskRequest,
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
) -> AskResponse:
    if not x_openai_key:
        raise HTTPException(
            status_code=401,
            detail=(
                "An OpenAI API key is required to ask questions. Profiling, "
                "insights, and correlations work without one."
            ),
        )

    session = session_or_404(session_id)
    settings = get_settings()

    sample = session.df.head(SAMPLE_ROWS).to_dict(orient="records")
    messages = build_prompt(payload.question, session.schema, sample, session.history)

    try:
        raw = ask_model(x_openai_key, settings.openai_model, messages)
        proposal = parse_response(raw)
    except LlmError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    # Logged after generation and before execution, so a blocked query is
    # still visible in the logs. The redaction filter keeps keys out.
    logger.info("Session %s generated SQL: %s", session_id, proposal.sql)

    try:
        result = run_query(
            session.conn, proposal.sql, row_limit=settings.default_row_limit
        )
    except SqlValidationError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except duckdb.Error as err:
        raise HTTPException(
            status_code=400,
            detail=f"The generated query did not run: {err}",
        ) from err

    chart = resolve_chart(proposal.chart, result)

    # Second call, once there is a result to describe. The first call happens
    # before anything has run, so it can only restate its own intent -- which
    # is why the old single-call answer read as "this query returns..." rather
    # than as an answer. Failure here is not fatal; the rows, chart, and SQL
    # are already in hand.
    answer = narrate(
        x_openai_key,
        settings.openai_model,
        payload.question,
        result.columns,
        result.rows,
        result.row_count,
    ) or proposal.explanation or f"{result.row_count} rows returned."

    session.add_turn(
        question=payload.question,
        sql=result.sql,
        summary=answer,
    )

    return AskResponse(
        question=payload.question,
        sql=result.sql,
        answer=answer,
        explanation=proposal.explanation,
        chart_requested=proposal.chart_requested,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        chart=chart,
    )

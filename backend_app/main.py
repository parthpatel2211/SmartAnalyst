import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_app.config import get_settings
from backend_app.logging_filters import RedactingFilter

DESCRIPTION = """\
Ask questions about a CSV in plain English.

SmartAnalyst translates each question into DuckDB SQL, validates that SQL
against an allowlist of read-only constructs, runs it, and returns the rows
alongside the query that produced them. Model output is never executed as
code.

Profiling, insights, and correlations require no API key. Only natural-language
questions do, and the key is supplied per request rather than held by the server.
"""


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    redactor = RedactingFilter()
    root = logging.getLogger()
    root.addFilter(redactor)
    # Filters on the root logger do not apply to records from child loggers,
    # so the handlers get one too.
    for handler in root.handlers:
        handler.addFilter(redactor)


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="SmartAnalyst API",
        description=DESCRIPTION,
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-OpenAI-Key"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe, also used by the frontend to detect a cold start."""
        return {"status": "ok"}

    return app


app = create_app()

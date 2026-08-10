# Python 3.11 rather than the newest release: it has the widest wheel
# coverage for pandas and DuckDB on slim images, which keeps the build from
# needing a compiler.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend_app ./backend_app
COPY data ./data

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# One worker deliberately: session state is process-local, so a second worker
# would serve requests that cannot see the uploaded dataset. See the README's
# known-limitations section.
CMD ["uvicorn", "backend_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

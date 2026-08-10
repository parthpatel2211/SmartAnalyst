"""Question-to-SQL translation.

The model writes a query; it never writes code, and nothing it returns is
executed as code. Its SQL still passes through :mod:`backend_app.sql_guard`
before reaching the database — the prompt's rules are guidance, not a
security control, because a prompt cannot be enforced.
"""

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from backend_app.models import ColumnSchema, QATurn

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_SAMPLE_ROWS = 3

SYSTEM_PROMPT = """\
You are a senior data analyst. You answer questions about a single DuckDB \
table named `data` by writing SQL.

Rules:
- Return a single SELECT (or WITH ... SELECT) statement. Never more than one \
statement. Never DDL, DML, ATTACH, COPY, PRAGMA, INSTALL, or LOAD.
- Never call file-reading functions such as read_csv or read_parquet.
- Preserve the exact case of string literals; the data is case-sensitive.
- Alias every computed column so the result is readable.
- Choose a chart that suits the shape of the result. Never choose a pie chart.
- If the question cannot be answered from these columns, still return valid \
SQL that comes closest, and say so in the explanation.

Respond with JSON only, in exactly this shape:
{"sql": "<the query>",
 "chart": {"kind": "bar|line|area|scatter|histogram|table",
           "x": "<column>", "y": ["<column>"], "series": null,
           "title": "<short title>"},
 "explanation": "<one sentence describing what the query returns>"}"""


class LlmError(RuntimeError):
    """The model returned something unusable, or the call failed."""


@dataclass(frozen=True)
class LlmResponse:
    sql: str
    chart: dict | None
    explanation: str


def build_prompt(
    question: str,
    schema: list[ColumnSchema],
    sample_rows: list[dict],
    history: list[QATurn],
) -> list[dict]:
    """Assemble the messages for one question.

    The schema carries semantic types rather than raw dtypes, so the model
    knows an order number is an identifier and should not be summed.
    """
    schema_lines = "\n".join(
        f"- {column.name} ({column.dtype}, {column.semantic_type}, "
        f"{column.distinct_count} distinct, {column.null_pct:.0f}% null)"
        for column in schema
    )

    parts = [f"Table `data` has these columns:\n{schema_lines}"]

    if sample_rows:
        sample = json.dumps(sample_rows[:MAX_SAMPLE_ROWS], default=str)
        parts.append(f"Sample rows:\n{sample}")

    if history:
        prior = "\n".join(
            f"Q: {turn.question}\nSQL: {turn.sql}\nResult: {turn.summary}"
            for turn in history
        )
        parts.append(
            f"Earlier in this conversation:\n{prior}\n"
            "Resolve references like 'that', 'those', or 'the same' against the above."
        )

    parts.append(f"Question: {question}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def parse_response(raw: str) -> LlmResponse:
    """Turn raw model output into a validated response, or raise."""
    cleaned = _FENCE.sub("", (raw or "").strip()).strip()
    if not cleaned:
        raise LlmError("The model returned an empty response. Try asking again.")

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise LlmError(
            "The model did not return valid JSON. Try rephrasing the question."
        ) from err

    if not isinstance(payload, dict) or not str(payload.get("sql", "")).strip():
        raise LlmError("The model did not return a SQL query for that question.")

    chart = payload.get("chart")
    return LlmResponse(
        sql=str(payload["sql"]).strip(),
        chart=chart if isinstance(chart, dict) else None,
        explanation=str(payload.get("explanation", "")).strip(),
    )


def ask_model(api_key: str, model: str, messages: list[dict]) -> str:
    """Make a single OpenAI call.

    The key is used here and nowhere else: not stored, not logged, not
    written to disk. Provider errors are reported by exception type only,
    because their messages sometimes echo the request, and the request
    carries the key.
    """
    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as err:
        raise LlmError(
            f"The language model call failed ({type(err).__name__}). "
            "Check that your API key is valid and has credit."
        ) from err

    return completion.choices[0].message.content or ""

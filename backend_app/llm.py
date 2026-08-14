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

#: OpenRouter issues keys with this prefix and speaks the OpenAI wire format at
#: its own host. Bring-your-own-key means the server cannot know in advance
#: which provider a caller's key belongs to, and sending it to the wrong host
#: produces an authentication error that looks like a bad key rather than a
#: misrouted request.
OPENROUTER_PREFIX = "sk-or-"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str | None
    model: str


def resolve_provider(api_key: str, model: str) -> Provider:
    """Pick the endpoint and model name that match the caller's key.

    OpenRouter namespaces its model ids by vendor, so a bare "gpt-4o-mini"
    has to become "openai/gpt-4o-mini" there while staying bare on OpenAI.
    """
    if api_key.startswith(OPENROUTER_PREFIX):
        routed = model if "/" in model else f"openai/{model}"
        return Provider(name="OpenRouter", base_url=OPENROUTER_BASE_URL, model=routed)

    # A vendor-prefixed id is meaningless to OpenAI directly; strip it.
    direct = model.split("/", 1)[-1] if "/" in model else model
    return Provider(name="OpenAI", base_url=None, model=direct)

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
    """Make a single completion call against whichever provider the key is for.

    The key is used here and nowhere else: not stored, not logged, not
    written to disk. Provider errors are reported by exception type and by
    which host was called, never by message, because provider messages
    sometimes echo the request and the request carries the key.
    """
    provider = resolve_provider(api_key, model)

    client = OpenAI(
        api_key=api_key,
        base_url=provider.base_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    try:
        completion = client.chat.completions.create(
            model=provider.model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as err:
        # Naming the provider matters: an authentication failure most often
        # means the key belongs to a different one, and a message that only
        # says "check your key is valid" sends people to look in the wrong
        # place entirely.
        raise LlmError(
            f"The {provider.name} call failed ({type(err).__name__}). "
            f"This key was sent to {provider.name}; check it belongs there, "
            "is still active, and has credit."
        ) from err

    return completion.choices[0].message.content or ""

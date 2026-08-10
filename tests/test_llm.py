import pytest

from backend_app.llm import LlmError, build_prompt, parse_response
from backend_app.models import ColumnSchema, QATurn

SCHEMA = [
    ColumnSchema(
        name="region", dtype="object", semantic_type="categorical",
        null_pct=0.0, distinct_count=4,
    ),
    ColumnSchema(
        name="revenue", dtype="float64", semantic_type="numeric",
        null_pct=0.0, distinct_count=500,
    ),
]


def _text(messages):
    return " ".join(m["content"] for m in messages)


def test_prompt_includes_schema_and_semantic_types():
    text = _text(build_prompt("total revenue by region", SCHEMA, [{"region": "N"}], []))
    assert "region" in text and "revenue" in text
    assert "categorical" in text and "numeric" in text


def test_prompt_includes_conversation_history():
    """Regression: the original code collected history but never sent it."""
    history = [QATurn(question="revenue by region", sql="SELECT 1", summary="Totals per region.")]
    text = _text(build_prompt("now only the West", SCHEMA, [], history))
    assert "revenue by region" in text
    assert "Totals per region." in text


def test_prompt_omits_the_history_block_when_there_is_none():
    text = _text(build_prompt("first question", SCHEMA, [], []))
    assert "Earlier in this conversation" not in text


def test_prompt_forbids_non_select_statements():
    text = _text(build_prompt("q", SCHEMA, [], []))
    assert "SELECT" in text
    assert "single" in text.lower()


def test_prompt_forbids_pie_charts():
    assert "pie" in _text(build_prompt("q", SCHEMA, [], [])).lower()


def test_prompt_carries_the_question():
    assert "how many orders" in _text(build_prompt("how many orders", SCHEMA, [], []))


def test_parses_clean_json():
    parsed = parse_response(
        '{"sql": "SELECT 1", "chart": {"kind": "bar"}, "explanation": "Ran it."}'
    )
    assert parsed.sql == "SELECT 1"
    assert parsed.chart == {"kind": "bar"}
    assert parsed.explanation == "Ran it."


def test_parses_json_wrapped_in_a_fenced_code_block():
    parsed = parse_response('```json\n{"sql": "SELECT 1", "explanation": "x"}\n```')
    assert parsed.sql == "SELECT 1"
    assert parsed.chart is None


def test_parses_json_in_a_bare_fence():
    assert parse_response('```\n{"sql": "SELECT 2", "explanation": ""}\n```').sql == "SELECT 2"


def test_non_dict_chart_is_discarded_rather_than_crashing():
    assert parse_response('{"sql": "SELECT 1", "chart": "bar"}').chart is None


def test_missing_sql_raises():
    with pytest.raises(LlmError):
        parse_response('{"explanation": "no query here"}')


def test_empty_sql_raises():
    with pytest.raises(LlmError):
        parse_response('{"sql": "", "explanation": "x"}')


def test_unparseable_output_raises():
    with pytest.raises(LlmError):
        parse_response("I'm sorry, I can't help with that.")


def test_empty_output_raises():
    with pytest.raises(LlmError):
        parse_response("")


def test_error_messages_are_user_facing():
    with pytest.raises(LlmError) as exc:
        parse_response("nonsense")
    assert "JSON" in str(exc.value) or "rephras" in str(exc.value).lower()

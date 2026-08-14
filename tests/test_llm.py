import pytest

from backend_app.llm import (
    OPENROUTER_BASE_URL,
    LlmError,
    build_prompt,
    parse_response,
    resolve_provider,
)
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


# --------------------------------------------------------------------------
# Provider routing
#
# Bring-your-own-key means the server cannot know which provider a caller's
# key belongs to. Sending an OpenRouter key to api.openai.com fails with an
# authentication error that reads like a bad key rather than a misrouted
# request, which is exactly the wrong thing to tell someone.
# --------------------------------------------------------------------------


def test_openai_key_goes_to_the_sdk_default_host():
    provider = resolve_provider("sk-proj-abc123", "gpt-4o-mini")
    assert provider.name == "OpenAI"
    assert provider.base_url is None


def test_openrouter_key_is_routed_to_openrouter():
    provider = resolve_provider("sk-or-v1-abc123", "gpt-4o-mini")
    assert provider.name == "OpenRouter"
    assert provider.base_url == OPENROUTER_BASE_URL


def test_openrouter_model_ids_are_vendor_namespaced():
    assert resolve_provider("sk-or-v1-abc", "gpt-4o-mini").model == "openai/gpt-4o-mini"


def test_an_already_namespaced_model_is_not_double_prefixed():
    assert (
        resolve_provider("sk-or-v1-abc", "anthropic/claude-3.5-sonnet").model
        == "anthropic/claude-3.5-sonnet"
    )


def test_namespace_is_stripped_when_calling_openai_directly():
    assert resolve_provider("sk-proj-abc", "openai/gpt-4o-mini").model == "gpt-4o-mini"


def test_provider_choice_depends_only_on_the_key_prefix():
    """The configured model must not change which host is called."""
    for model in ("gpt-4o-mini", "gpt-4o", "openai/gpt-4o"):
        assert resolve_provider("sk-or-v1-x", model).name == "OpenRouter"
        assert resolve_provider("sk-svcacct-x", model).name == "OpenAI"

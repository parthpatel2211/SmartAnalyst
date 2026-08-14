import io
import json

import pytest
from fastapi.testclient import TestClient

from backend_app.main import create_app

CSV = b"region,revenue\nNorth,100\nSouth,200\nNorth,150\n"
KEY = {"X-OpenAI-Key": "sk-test-key-not-real-000000000000"}


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def session_id(client):
    response = client.post("/datasets", files={"file": ("t.csv", io.BytesIO(CSV), "text/csv")})
    return response.json()["session_id"]


@pytest.fixture(autouse=True)
def _no_real_narration(monkeypatch):
    """Stub the narration call in every test.

    Without this each request would reach out to a real provider with a fake
    key and sit on the timeout before falling back.
    """
    monkeypatch.setattr(
        "backend_app.routers.ask.narrate",
        lambda *args, **kwargs: "West leads at 2.6M.",
    )


def _mock_model(monkeypatch, payload: dict):
    monkeypatch.setattr(
        "backend_app.routers.ask.ask_model",
        lambda api_key, model, messages: json.dumps(payload),
    )


def test_happy_path_returns_rows_sql_and_chart(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {
            "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
            "chart": {"kind": "bar", "x": "region", "y": ["total"], "title": "Revenue by region"},
            "explanation": "Total revenue per region.",
        },
    )
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "revenue by region"}, headers=KEY
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chart"]["kind"] == "bar"
    assert body["row_count"] == 2
    assert "GROUP BY" in body["sql"].upper()
    assert body["explanation"] == "Total revenue per region."
    assert body["truncated"] is False


def test_missing_api_key_returns_401(client, session_id):
    response = client.post(f"/datasets/{session_id}/ask", json={"question": "anything"})
    assert response.status_code == 401
    assert "key" in response.json()["detail"].lower()


def test_dangerous_generated_sql_is_blocked(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "SELECT 1; DROP TABLE data", "chart": None, "explanation": "oops"},
    )
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "delete everything"}, headers=KEY
    )
    assert response.status_code == 400
    assert "statement" in response.json()["detail"].lower()


def test_data_survives_a_blocked_query(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {"sql": "DROP TABLE data", "chart": None, "explanation": ""})
    client.post(f"/datasets/{session_id}/ask", json={"question": "drop"}, headers=KEY)

    _mock_model(
        monkeypatch,
        {"sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "count"},
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "count"}, headers=KEY
    ).json()
    assert body["rows"][0]["n"] == 3


def test_file_reading_function_is_blocked(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {
            "sql": "SELECT * FROM read_csv_auto('/etc/passwd')",
            "chart": None,
            "explanation": "",
        },
    )
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "read a file"}, headers=KEY
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"].lower()


def test_invalid_chart_spec_falls_back_instead_of_failing(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {
            "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
            "chart": {"kind": "bar", "x": "nonexistent", "y": ["total"], "title": "T"},
            "explanation": "x",
        },
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    ).json()
    assert body["chart"]["x"] == "region"


def test_a_query_that_fails_to_run_returns_400_not_500(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "SELECT no_such_column FROM data", "chart": None, "explanation": "x"},
    )
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    )
    assert response.status_code == 400


def test_unusable_model_output_returns_502(client, session_id, monkeypatch):
    monkeypatch.setattr(
        "backend_app.routers.ask.ask_model",
        lambda api_key, model, messages: "I'm sorry, I can't help with that.",
    )
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    )
    assert response.status_code == 502


def test_conversation_history_is_sent_to_the_model(client, session_id, monkeypatch):
    """Regression: the prototype recorded history but never included it in the
    prompt, so follow-up questions could not resolve references."""
    _mock_model(
        monkeypatch,
        {"sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "counted rows"},
    )
    client.post(f"/datasets/{session_id}/ask", json={"question": "count"}, headers=KEY)

    captured = {}

    def capture(api_key, model, messages):
        captured["text"] = " ".join(m["content"] for m in messages)
        return json.dumps({"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})

    monkeypatch.setattr("backend_app.routers.ask.ask_model", capture)
    client.post(f"/datasets/{session_id}/ask", json={"question": "again"}, headers=KEY)

    # The prior question and the finding both travel, so "filter that to the
    # West" has something concrete to resolve against.
    assert "count" in captured["text"]
    assert "West leads at 2.6M." in captured["text"]
    assert "SELECT COUNT(*)" in captured["text"]


def test_the_key_reaches_the_model_call_unchanged(client, session_id, monkeypatch):
    captured = {}

    def capture(api_key, model, messages):
        captured["key"] = api_key
        return json.dumps({"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})

    monkeypatch.setattr("backend_app.routers.ask.ask_model", capture)
    client.post(f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY)
    assert captured["key"] == KEY["X-OpenAI-Key"]


def test_api_key_is_not_echoed_in_any_response(client, session_id, monkeypatch):
    _mock_model(monkeypatch, {"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})
    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    )
    assert KEY["X-OpenAI-Key"] not in response.text


def test_unknown_session_returns_404(client):
    response = client.post("/datasets/nope/ask", json={"question": "q"}, headers=KEY)
    assert response.status_code == 404


def test_answer_states_the_finding_not_the_query(client, session_id, monkeypatch):
    """The first call writes SQL before anything has run, so it can only
    describe intent. The answer comes from a second call that sees results."""
    _mock_model(
        monkeypatch,
        {
            "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
            "chart": None,
            "explanation": "This query returns revenue per region.",
        },
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "top region"}, headers=KEY
    ).json()

    assert body["answer"] == "West leads at 2.6M."
    assert body["explanation"] == "This query returns revenue per region."


def test_narration_receives_the_actual_result_rows(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "SELECT region FROM data LIMIT 2", "chart": None, "explanation": "x"},
    )
    captured = {}

    def capture(api_key, model, question, columns, rows, row_count):
        captured.update(question=question, columns=columns, row_count=row_count)
        return "answered"

    monkeypatch.setattr("backend_app.routers.ask.narrate", capture)
    client.post(f"/datasets/{session_id}/ask", json={"question": "which regions"}, headers=KEY)

    assert captured["question"] == "which regions"
    assert captured["columns"] == ["region"]
    assert captured["row_count"] == 2


def test_a_failed_narration_does_not_lose_the_answer(client, session_id, monkeypatch):
    """Rows, chart, and SQL are already in hand; narration is a nicety."""
    _mock_model(
        monkeypatch,
        {"sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "counts rows"},
    )
    monkeypatch.setattr("backend_app.routers.ask.narrate", lambda *a, **k: "")

    response = client.post(
        f"/datasets/{session_id}/ask", json={"question": "how many"}, headers=KEY
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "counts rows"
    assert body["rows"][0]["n"] == 3


def test_chart_requested_defaults_to_false(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "SELECT region FROM data", "chart": None, "explanation": "x"},
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "which regions"}, headers=KEY
    ).json()
    assert body["chart_requested"] is False


def test_chart_requested_is_carried_through(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {
            "sql": "SELECT region, SUM(revenue) AS total FROM data GROUP BY region",
            "chart": {"kind": "bar", "x": "region", "y": ["total"], "title": "T"},
            "chart_requested": True,
            "explanation": "x",
        },
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "chart revenue by region"}, headers=KEY
    ).json()
    assert body["chart_requested"] is True


def test_history_records_the_answer_rather_than_the_query_description(
    client, session_id, monkeypatch
):
    _mock_model(
        monkeypatch,
        {"sql": "SELECT COUNT(*) AS n FROM data", "chart": None, "explanation": "describes"},
    )
    client.post(f"/datasets/{session_id}/ask", json={"question": "count"}, headers=KEY)

    captured = {}

    def capture(api_key, model, messages):
        captured["text"] = " ".join(m["content"] for m in messages)
        return json.dumps({"sql": "SELECT 1 AS n", "chart": None, "explanation": "x"})

    monkeypatch.setattr("backend_app.routers.ask.ask_model", capture)
    client.post(f"/datasets/{session_id}/ask", json={"question": "again"}, headers=KEY)

    assert "West leads at 2.6M." in captured["text"]


def test_returned_sql_is_the_query_that_ran(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "select   region from data", "chart": None, "explanation": "x"},
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    ).json()
    assert body["sql"] == "SELECT region FROM data"

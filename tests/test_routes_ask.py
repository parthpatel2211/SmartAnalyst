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

    assert "counted rows" in captured["text"]
    assert "count" in captured["text"]


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


def test_returned_sql_is_the_query_that_ran(client, session_id, monkeypatch):
    _mock_model(
        monkeypatch,
        {"sql": "select   region from data", "chart": None, "explanation": "x"},
    )
    body = client.post(
        f"/datasets/{session_id}/ask", json={"question": "q"}, headers=KEY
    ).json()
    assert body["sql"] == "SELECT region FROM data"

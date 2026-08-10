import io

import pytest
from fastapi.testclient import TestClient

from backend_app.main import create_app

CSV = b"region,revenue,cost\nNorth,100,60\nSouth,200,120\nNorth,150,90\n"


@pytest.fixture
def client():
    return TestClient(create_app())


def _upload(client, data=CSV, filename="t.csv", content_type="text/csv"):
    return client.post(
        "/datasets", files={"file": (filename, io.BytesIO(data), content_type)}
    )


def test_upload_returns_session_and_schema(client):
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["session_id"]
    assert body["row_count"] == 3
    assert body["column_count"] == 3
    # Named "columns" rather than "schema": a field called schema shadows
    # BaseModel.schema in Pydantic v2.
    assert {c["name"] for c in body["columns"]} == {"region", "revenue", "cost"}
    assert {c["semantic_type"] for c in body["columns"]} <= {
        "id", "categorical", "numeric", "datetime", "boolean", "text",
    }


def test_registered_routes_exist():
    """Regression: /profile and /nl2sql were never registered in the original app.

    Both modules defined an APIRouter, but nothing ever called
    include_router, so two thirds of the advertised feature set was
    unreachable code.
    """
    paths = {route.path for route in create_app().routes}
    assert "/datasets" in paths
    assert "/datasets/{session_id}/profile" in paths
    assert "/datasets/{session_id}/insights" in paths
    assert "/datasets/{session_id}/correlations" in paths
    assert "/datasets/{session_id}/ask" in paths


def test_profile_returns_real_statistics(client):
    """Regression: the original /profile bound the dataframe by value at import
    time, so it was permanently None and always answered 'no data uploaded'."""
    sid = _upload(client).json()["session_id"]
    body = client.get(f"/datasets/{sid}/profile").json()
    assert body["row_count"] == 3
    revenue = next(c for c in body["columns"] if c["name"] == "revenue")
    assert revenue["median"] == 150
    assert revenue["semantic_type"] == "numeric"


def test_insights_endpoint_returns_a_list(client):
    sid = _upload(client).json()["session_id"]
    response = client.get(f"/datasets/{sid}/insights")
    assert response.status_code == 200
    assert isinstance(response.json()["insights"], list)


def test_correlations_endpoint(client):
    sid = _upload(client).json()["session_id"]
    body = client.get(f"/datasets/{sid}/correlations").json()
    assert set(body["columns"]) == {"revenue", "cost"}


def test_two_uploads_do_not_share_data(client):
    """The prototype's global dataframe meant the last upload won for everyone."""
    first = _upload(client, b"a\n1\n").json()["session_id"]
    second = _upload(client, b"b\n1\n2\n").json()["session_id"]
    assert client.get(f"/datasets/{first}/profile").json()["row_count"] == 1
    assert client.get(f"/datasets/{second}/profile").json()["row_count"] == 2


def test_unknown_session_returns_404(client):
    assert client.get("/datasets/does-not-exist/profile").status_code == 404
    assert client.get("/datasets/does-not-exist/insights").status_code == 404
    assert client.get("/datasets/does-not-exist/correlations").status_code == 404


def test_unparseable_upload_returns_400(client):
    response = _upload(client, b"\x00\x01\x02binary", "x.bin", "application/octet-stream")
    assert response.status_code in (400, 413)


def test_empty_upload_is_rejected(client):
    assert _upload(client, b"").status_code in (400, 413)


def test_analysis_endpoints_need_no_api_key(client):
    """Profiling must work with no key so a first-time visitor sees real output
    before being asked for anything."""
    sid = _upload(client).json()["session_id"]
    for path in ("profile", "insights", "correlations"):
        response = client.get(f"/datasets/{sid}/{path}")
        assert response.status_code == 200, path


def test_health_still_works(client):
    assert client.get("/health").json() == {"status": "ok"}

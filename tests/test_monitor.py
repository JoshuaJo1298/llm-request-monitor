import json
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app import app
from seed import incident


@pytest.fixture
def client(monkeypatch):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("set TEST_DATABASE_URL to run PostgreSQL integration tests")
    schema = "test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        monkeypatch.setenv("DATABASE_URL", make_conninfo(dsn, options=f"-c search_path={schema}"))
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_incident_reimport_and_filters(client):
    assert client.get("/api/metrics").json() == []
    records = list(incident())
    body = "\n".join(["{broken", *(json.dumps(row) for row in records), "{}"])
    imported = client.post("/api/import", content=body)
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["inserted"] == 96
    assert [line["line"] for line in payload["rejected"]] == [1, 98]
    expected = client.get("/api/metrics").json()
    assert expected[0] == {"model": "aurora-large", "requests": 48, "error_rate": 3 / 48, "p95_ms": 3014}
    assert client.get("/api/metrics?window=15m").json()[0]["requests"] < 48
    duplicates = client.post("/api/import", content=body).json()
    assert duplicates["duplicates"] == 96 and duplicates["inserted"] == 0
    assert client.get("/api/metrics").json() == expected
    assert "3,014 ms" in client.get("/").text


def test_invalid_input(client):
    row = next(incident())
    row.pop("occurred_at")
    result = client.post("/api/import", content=json.dumps(row)).json()
    assert result["inserted"] == 0 and result["rejected"][0]["line"] == 1
    assert client.post("/api/import", content=b"\xff").status_code == 400
    assert client.post("/api/import", content=b"x" * 2_000_001).status_code == 413
    assert client.get("/api/metrics?window=invalid").status_code == 422

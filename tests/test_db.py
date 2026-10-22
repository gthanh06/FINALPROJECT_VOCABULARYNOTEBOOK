# tests/test_db.py — what happens when the database is paused or unreachable.
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import DB_DOWN_MESSAGE, app
from app.routes import get_repo


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(db.time, "sleep", lambda s: None)


def test_connect_retries_then_succeeds(monkeypatch):
    calls = []

    def flaky_connect(url, **kwargs):
        calls.append(url)
        if len(calls) < 3:
            raise psycopg.OperationalError("server is starting up")
        return "connection"

    monkeypatch.setattr(db.psycopg, "connect", flaky_connect)
    assert db.connect("postgresql://x") == "connection"
    assert len(calls) == 3


def test_connect_gives_up_after_all_attempts(monkeypatch):
    def always_down(url, **kwargs):
        raise psycopg.OperationalError("could not translate host name")

    monkeypatch.setattr(db.psycopg, "connect", always_down)
    with pytest.raises(db.DatabaseUnavailable):
        db.connect("postgresql://x")


def test_api_returns_friendly_503_when_db_down():
    def db_down():
        raise db.DatabaseUnavailable

    app.dependency_overrides[get_repo] = db_down
    try:
        r = TestClient(app).get("/api/words")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json() == {"detail": DB_DOWN_MESSAGE}


def test_health_does_not_touch_db():
    assert TestClient(app).get("/health").json() == {"status": "ok"}

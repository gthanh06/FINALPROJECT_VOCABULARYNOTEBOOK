# tests/test_ui.py — the web UI is served by the same app as the API.
from fastapi.testclient import TestClient

from app.main import app


def test_home_serves_the_ui():
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    for page in ('id="tpl-list"', 'id="tpl-form"', 'id="tpl-review"'):
        assert page in r.text


def test_static_assets_are_served():
    client = TestClient(app)
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_info_reports_version_and_env():
    body = TestClient(app).get("/api/info").json()
    assert body["app"] == "vocab-notebook"
    assert body["env"] == "test"

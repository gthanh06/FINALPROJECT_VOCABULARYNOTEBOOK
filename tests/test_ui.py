# tests/test_ui.py — the web UI is served by the same app as the API.
import re

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


def test_ui_is_revalidated_after_each_deploy():
    client = TestClient(app)
    for path in ("/", "/static/app.js", "/static/style.css"):
        assert client.get(path).headers["cache-control"] == "no-cache"


def test_asset_urls_change_with_their_content():
    html = TestClient(app).get("/").text
    assert re.search(r'"/static/app\.js\?v=[0-9a-f]{10}"', html)
    assert re.search(r'"/static/style\.css\?v=[0-9a-f]{10}"', html)

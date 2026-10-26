# tests/test_auth.py — accounts, sessions, and one notebook per user.
from fastapi.testclient import TestClient

from app.main import app
from app.security import SESSION_COOKIE, hash_password, verify_password
from tests.conftest import PASSWORD, register


def add_apple(admin):
    return admin.post("/api/words", json={"word": "apple", "meaning_vi": "quả táo"}).json()["id"]


def login(client, email="an@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_password_hash_round_trip():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$")
    assert "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong-pass", stored)
    assert hash_password("s3cret-pass") != stored  # random salt each time


def test_register_logs_in_and_hides_the_hash(anon):
    r = register(anon)
    body = r.json()
    assert body["email"] == "an@example.com"
    assert "password_hash" not in body
    cookie = r.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert anon.get("/api/auth/me").json()["display_name"] == "An"


def test_register_validates_input(anon):
    bad = [
        {"email": "not-an-email", "display_name": "An", "password": PASSWORD},
        {"email": "an@example.com", "display_name": "An", "password": "short"},
        {"email": "an@example.com", "display_name": "", "password": PASSWORD},
    ]
    for body in bad:
        assert anon.post("/api/auth/register", json=body).status_code == 422


def test_email_can_only_register_once(anon):
    register(anon)
    r = anon.post(
        "/api/auth/register",
        json={"email": "AN@example.com", "display_name": "X", "password": PASSWORD},
    )
    assert r.status_code == 409


def test_login_and_logout(anon):
    register(anon)
    anon.post("/api/auth/logout")
    assert anon.get("/api/auth/me").status_code == 401

    assert login(anon).status_code == 200
    assert anon.get("/api/auth/me").status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(anon):
    register(anon)
    anon.post("/api/auth/logout")
    wrong = login(anon, password="wrong-password")
    unknown = login(anon, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_logout_revokes_the_session_on_the_server(anon, users):
    register(anon)
    token = anon.cookies[SESSION_COOKIE]
    anon.post("/api/auth/logout")
    # Even if someone kept a copy of the old cookie, it no longer works.
    stolen = TestClient(app, cookies={SESSION_COOKIE: token})
    assert stolen.get("/api/words").status_code == 401
    assert users.sessions == {}


def test_words_need_login(anon):
    assert anon.get("/api/words").status_code == 401
    assert anon.post("/api/words", json={"word": "a", "meaning_vi": "b"}).status_code == 401
    assert anon.delete("/api/words/1").status_code == 401


def test_new_accounts_are_learners(anon):
    assert register(anon).json()["role"] == "learner"


def test_learners_cannot_change_words(client, learner):
    word_id = add_apple(client)
    assert learner.post("/api/words", json={"word": "pear", "meaning_vi": "lê"}).status_code == 403
    assert learner.patch(f"/api/words/{word_id}", json={"meaning_vi": "x"}).status_code == 403
    assert learner.delete(f"/api/words/{word_id}").status_code == 403
    assert client.get(f"/api/words/{word_id}").json()["meaning_vi"] == "quả táo"


def test_everyone_studies_the_admins_words(client, learner):
    add_apple(client)
    assert [w["word"] for w in learner.get("/api/words").json()] == ["apple"]


def test_practice_history_is_per_user(client, learner):
    word_id = add_apple(client)
    learner.post(f"/api/words/{word_id}/reviews", json={"result": "forgot"})
    assert len(learner.get(f"/api/words/{word_id}/reviews").json()) == 1
    assert client.get(f"/api/words/{word_id}/reviews").json() == []


def test_admin_sees_learners_progress(client, learner):
    word_id = add_apple(client)
    learner.post(f"/api/words/{word_id}/reviews", json={"result": "remembered"})
    learner.post(f"/api/words/{word_id}/reviews", json={"result": "forgot"})
    rows = {u["email"]: u for u in client.get("/api/admin/users").json()}
    assert rows["learner@example.com"]["review_count"] == 2
    assert rows["learner@example.com"]["remembered_count"] == 1
    assert "password_hash" not in rows["learner@example.com"]
    assert learner.get("/api/admin/users").status_code == 403


def test_ensure_admin_creates_or_promotes(users):
    created = users.ensure_admin("boss@example.com", "Admin", hash_password("admin-pass-1"))
    assert created["role"] == "admin"
    learner = users.create_user("lan@example.com", "Lan", hash_password("old-password"))
    promoted = users.ensure_admin("LAN@example.com", "Admin", hash_password("new-password"))
    assert promoted["id"] == learner["id"]
    assert promoted["role"] == "admin"
    assert verify_password("new-password", promoted["password_hash"])

# tests/test_auth.py — accounts, sessions, and one notebook per user.
from fastapi.testclient import TestClient

from app.main import app
from app.security import SESSION_COOKIE, hash_password, verify_password
from tests.conftest import PASSWORD, register


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


def test_new_account_gets_the_starter_words(anon, repo):
    repo.starter = [{"word": "hello", "meaning_vi": "xin chào", "part_of_speech": None,
                     "example": None, "usage_note": None}]
    register(anon)
    assert [w["word"] for w in anon.get("/api/words").json()] == ["hello"]


def test_users_only_see_their_own_words(anon):
    register(anon, email="an@example.com")
    an_word = anon.post("/api/words", json={"word": "apple", "meaning_vi": "quả táo"}).json()
    anon.post("/api/auth/logout")

    register(anon, email="binh@example.com", name="Bình")
    assert anon.get("/api/words").json() == []
    assert anon.get(f"/api/words/{an_word['id']}").status_code == 404
    assert anon.delete(f"/api/words/{an_word['id']}").status_code == 404
    # Each notebook has its own words, so Bình can save "apple" too.
    assert anon.post("/api/words", json={"word": "apple", "meaning_vi": "táo"}).status_code == 201

# tests/test_progress.py — a learner's own progress, and the admin-only sign-in.
from tests.conftest import PASSWORD, register

DOG = {"word": "dog", "meaning_vi": "con chó", "topic_id": 1}
CAT = {"word": "cat", "meaning_vi": "con mèo", "topic_id": 1}
SOFA = {"word": "sofa", "meaning_vi": "ghế sofa", "topic_id": 2}


def answer(client, word_id, *results):
    for result in results:
        client.post(f"/api/words/{word_id}/reviews", json={"result": result})


def test_progress_counts_my_answers(client, learner):
    dog, cat, sofa = (client.post("/api/words", json=w).json()["id"] for w in (DOG, CAT, SOFA))
    answer(learner, dog, "forgot", "remembered")  # learned it in the end -> mastered
    answer(learner, cat, "remembered", "forgot")  # forgot it last time -> to review
    p = learner.get("/api/me/progress").json()
    assert (p["answered"], p["correct"], p["practiced"], p["mastered"]) == (4, 2, 2, 1)
    assert p["total_words"] == 3
    animals = next(t for t in p["topics"] if t["slug"] == "animals")
    assert (animals["total"], animals["practiced"], animals["mastered"]) == (2, 2, 1)
    assert [w["word"] for w in p["to_review"]] == ["cat"]
    assert len(p["last_7_days"]) == 7
    assert p["last_7_days"][-1]["answered"] == 4  # today
    assert sofa not in [w["id"] for w in p["to_review"]]


def test_progress_is_private(client, learner):
    dog = client.post("/api/words", json=DOG).json()["id"]
    answer(learner, dog, "remembered")
    assert client.get("/api/me/progress").json()["answered"] == 0


def test_progress_needs_login(anon):
    assert anon.get("/api/me/progress").status_code == 401


def test_admin_sign_in_rejects_learners(anon, users):
    register(anon, email="lan@example.com")
    anon.post("/api/auth/logout")
    r = anon.post(
        "/api/auth/login", json={"email": "lan@example.com", "password": PASSWORD, "admin": True}
    )
    assert r.status_code == 403
    # No session was started: the learner is still logged out.
    assert anon.get("/api/auth/me").status_code == 401


def test_admin_sign_in_accepts_admins(anon, users):
    user = register(anon, email="boss@example.com").json()
    users.users[user["id"]]["role"] = "admin"
    anon.post("/api/auth/logout")
    r = anon.post(
        "/api/auth/login", json={"email": "boss@example.com", "password": PASSWORD, "admin": True}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_nobody_can_register_as_admin(anon):
    body = {"email": "x@example.com", "display_name": "X", "password": PASSWORD, "role": "admin"}
    assert anon.post("/api/auth/register", json=body).json()["role"] == "learner"

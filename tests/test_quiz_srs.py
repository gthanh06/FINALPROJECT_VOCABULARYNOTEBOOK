from datetime import UTC, date, datetime

from app.srs import schedule, vietnam_today
from tests.conftest import register


def add_words(client):
    examples = [
        ("apple", "quả táo", "I eat an apple."),
        ("book", "quyển sách", "I read a book."),
        ("cat", "con mèo", "A cat sleeps."),
        ("river", "dòng sông", "The river is wide."),
    ]
    for word, meaning, example in examples:
        response = client.post(
            "/api/notebook/words",
            json={"word": word, "meaning_vi": meaning, "examples": [{"en": example}]},
        )
        assert response.status_code == 201, response.text


def test_srs_schedule_progression_and_failed_recall():
    first = schedule(0, 2.5, 0, 5, date(2026, 11, 2))
    assert first == {
        "level": 1, "ease": 2.6, "interval_days": 1, "next_review": date(2026, 11, 3),
    }
    second = schedule(first["level"], first["ease"], first["interval_days"], 4, date(2026, 11, 3))
    assert second["level"] == 2 and second["interval_days"] == 6
    failed = schedule(4, 1.3, 30, 0, date(2026, 11, 9))
    assert failed["level"] == 0 and failed["interval_days"] == 1 and failed["ease"] == 1.3


def test_vietnamese_day_rollover():
    assert vietnam_today(datetime(2026, 11, 1, 17, 30, tzinfo=UTC)) == date(2026, 11, 2)


def test_srs_due_cards_are_private_and_reviews_reschedule(learner, new_browser, repo):
    add_words(learner)
    today = learner.get("/api/srs/today")
    assert today.status_code == 200 and today.json()["due"] == 4
    reviewed = learner.post("/api/srs/words/1/review", json={"quality": 5})
    assert reviewed.status_code == 200
    assert reviewed.json()["level"] == 1 and reviewed.json()["interval_days"] == 1
    assert learner.get("/api/srs/today").json()["due"] == 3
    history = learner.get("/api/srs/words/1/reviews")
    assert history.status_code == 200
    assert history.json()[0]["quality"] == 5

    other = new_browser()
    register(other, email="srs-other@example.com", name="Other")
    assert other.get("/api/srs/today").json()["due"] == 0
    assert other.post("/api/srs/words/1/review", json={"quality": 2}).status_code == 404
    assert other.get("/api/srs/words/1/reviews").status_code == 404
    assert len(repo.srs_reviews) == 1


def test_srs_requires_login_and_valid_quality(anon, learner):
    assert anon.get("/api/srs/today").status_code == 401
    assert anon.post("/api/srs/words/1/review", json={"quality": 4}).status_code == 401
    assert learner.post("/api/srs/words/1/review", json={"quality": 6}).status_code == 422


def test_quiz_creates_server_hidden_answer_key_and_grades_on_submit(learner, repo):
    add_words(learner)
    started = learner.post("/api/quiz", json={"count": 3})
    assert started.status_code == 201, started.text
    body = started.json()
    assert len(body["questions"]) == 3
    assert {q["kind"] for q in body["questions"]} == {
        "multiple_choice", "fill_blank", "meaning",
    }
    assert all("answer" not in q and "expected" not in q for q in body["questions"])

    wrong_answers = [
        {"question_id": q["id"], "answer": "not the answer"} for q in body["questions"]
    ]
    response = learner.post(
        f"/api/quiz/{body['quiz_id']}/submit", json={"answers": wrong_answers}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 3 and result["score"] == 0
    assert all(q["expected"] for q in result["questions"])
    assert learner.post(
        f"/api/quiz/{body['quiz_id']}/submit",
        json={"answers": [{"question_id": q["id"], "answer": "x"} for q in body["questions"]]},
    ).status_code == 409

    next_quiz = learner.post("/api/quiz", json={"count": 3}).json()
    answer_key = repo.quizzes[next_quiz["quiz_id"]]["questions"]
    correct = learner.post(
        f"/api/quiz/{next_quiz['quiz_id']}/submit",
        json={"answers": [
            {"question_id": question["id"], "answer": question["answer"]}
            for question in answer_key
        ]},
    )
    assert correct.status_code == 200 and correct.json()["score"] == 3


def test_quiz_is_private_requires_three_words_and_rejects_bad_submissions(learner, new_browser):
    assert learner.post("/api/quiz").status_code == 422
    for word, meaning in [("apple", "quả táo"), ("book", "sách"), ("cat", "mèo")]:
        learner.post("/api/notebook/words", json={"word": word, "meaning_vi": meaning})
    started = learner.post("/api/quiz", json={"count": 3})
    assert started.status_code == 201
    quiz = started.json()
    assert learner.post(
        f"/api/quiz/{quiz['quiz_id']}/submit", json={"answers": []}
    ).status_code == 422
    other = new_browser()
    register(other, email="quiz-other@example.com", name="Other")
    assert other.post(
        f"/api/quiz/{quiz['quiz_id']}/submit",
        json={"answers": [{"question_id": q["id"], "answer": "x"} for q in quiz["questions"]]},
    ).status_code == 404


def test_quiz_requires_login(anon):
    assert anon.post("/api/quiz").status_code == 401
    assert anon.post("/api/quiz/1/submit", json={"answers": []}).status_code == 401


def test_mnemonic_is_generated_and_cached_for_matching_words(learner, new_browser, ai):
    word = {"word": "resilient", "meaning_vi": "kiên cường"}
    assert learner.post("/api/notebook/words", json=word).status_code == 201
    ai.queue({"mnemonic": "Tưởng tượng một chiếc lò xo bật lại sau khi bị nén."})
    first = learner.post("/api/srs/words/1/mnemonic")
    assert first.status_code == 200, first.text
    assert first.json()["cached"] is False

    other = new_browser()
    register(other, email="mnemonic-other@example.com", name="Other")
    other_word = other.post("/api/notebook/words", json=word)
    assert other_word.status_code == 201
    second = other.post(f"/api/srs/words/{other_word.json()['id']}/mnemonic")
    assert second.status_code == 200, second.text
    assert second.json()["cached"] is True
    assert len(ai.calls) == 1

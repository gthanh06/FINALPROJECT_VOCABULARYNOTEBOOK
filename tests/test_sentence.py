# tests/test_sentence.py — POST /api/ai/check-sentence: grading a sentence the learner wrote.
from tests.conftest import register
from tests.fake_ai import sentence_answer

WORD = {"word": "resilient", "meaning_vi": "kiên cường", "part_of_speech": "adjective"}


def add_word(browser):
    r = browser.post("/api/notebook/words", json=WORD)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def check(browser, word_id, sentence):
    return browser.post("/api/ai/check-sentence", json={"word_id": word_id, "sentence": sentence})


def test_wrong_sentence_is_explained_in_vietnamese(learner, ai):
    word_id = add_word(learner)
    ai.queue(sentence_answer())
    r = check(learner, word_id, "She  very resilient.")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cached"] is False
    result = body["result"]
    assert result["verdict"] == "incorrect"
    assert result["errors"][0]["explanation_vi"].startswith("Thiếu động từ")
    assert result["corrected"] == "She is very resilient."
    prompt = ai.calls[0]["prompt"]
    assert "Target word: resilient (adjective)" in prompt
    assert "kiên cường" in prompt
    # Extra spaces are collapsed before grading.
    assert "<<<\nShe very resilient.\n>>>" in prompt


def test_same_sentence_again_is_cached(learner, ai):
    word_id = add_word(learner)
    ai.queue(sentence_answer("correct"))
    check(learner, word_id, "She is very resilient.")
    r = check(learner, word_id, "She is very resilient.")
    assert r.json()["cached"] is True
    assert r.json()["result"]["verdict"] == "correct"
    assert len(ai.calls) == 1


def test_wrong_verdict_without_errors_is_retried(learner, ai):
    word_id = add_word(learner)
    ai.queue(sentence_answer(errors=[]), sentence_answer())
    assert check(learner, word_id, "She resilient.").status_code == 200
    assert len(ai.calls) == 2


def test_only_my_own_words(learner, new_browser, ai):
    word_id = add_word(learner)
    other = new_browser()
    register(other, email="binh@example.com", name="Bình")
    assert check(other, word_id, "She is resilient.").status_code == 404
    assert check(learner, 999, "She is resilient.").status_code == 404
    assert ai.calls == []


def test_sentence_length_is_checked(learner, ai):
    word_id = add_word(learner)
    assert check(learner, word_id, "").status_code == 422
    assert check(learner, word_id, "x" * 301).status_code == 422
    assert check(learner, word_id, "   a   ").status_code == 422
    assert ai.calls == []


def test_counts_towards_the_limit(learner, ai, monkeypatch):
    monkeypatch.setenv("AI_LIMIT_PER_MINUTE", "1")
    word_id = add_word(learner)
    ai.queue(sentence_answer())
    assert check(learner, word_id, "She resilient.").status_code == 200
    assert check(learner, word_id, "She are resilient.").status_code == 429


def test_needs_login(anon):
    body = {"word_id": 1, "sentence": "Hi there"}
    assert anon.post("/api/ai/check-sentence", json=body).status_code == 401

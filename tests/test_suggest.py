# tests/test_suggest.py — POST /api/ai/suggest-words: new words for a topic and a CEFR level.
from tests.fake_ai import suggest_answer

ANIMALS = 1  # topic ids from tests/fake_repo.py


def suggest(browser, exclude=(), level="B1", topic_id=ANIMALS):
    return browser.post(
        "/api/ai/suggest-words",
        json={"topic_id": topic_id, "level": level, "exclude": list(exclude)},
    )


def test_suggests_words_for_the_topic_and_level(learner, ai):
    ai.queue(suggest_answer("otter", "beaver", "hedgehog"))
    r = suggest(learner)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [w["word"] for w in body["words"]] == ["otter", "beaver", "hedgehog"]
    assert body["topic_id"] == ANIMALS
    assert body["words"][0]["example"]["vi"]
    prompt = ai.calls[0]["prompt"]
    assert "Topic: Con vật" in prompt
    assert "Level: B1" in prompt
    assert "Leave out: (none)" in prompt


def test_words_already_in_my_notebook_are_left_out(learner, ai):
    learner.post("/api/notebook/words", json={"word": "Otter", "meaning_vi": "rái cá"})
    ai.queue(suggest_answer("otter", "beaver", "hedgehog", "Beaver", "not a word!"))
    words = [w["word"] for w in suggest(learner).json()["words"]]
    assert words == ["beaver", "hedgehog"]
    assert "Leave out: otter" in ai.calls[0]["prompt"]


def test_first_list_is_cached_more_is_fresh(learner, new_browser, ai):
    ai.queue(suggest_answer("otter", "beaver", "hedgehog"))
    assert suggest(learner).json()["cached"] is False
    assert suggest(learner).json()["cached"] is True
    assert len(ai.calls) == 1

    ai.queue(suggest_answer("otter", "badger", "ferret", "mole"))
    body = suggest(learner, exclude=["otter", "beaver", "hedgehog"]).json()
    assert body["cached"] is False
    assert [w["word"] for w in body["words"]] == ["badger", "ferret", "mole"]
    assert "beaver, hedgehog, otter" in ai.calls[1]["prompt"]


def test_cached_list_without_enough_new_words_asks_again(learner, ai):
    ai.queue(suggest_answer("otter", "beaver", "hedgehog"))
    suggest(learner)
    for word in ("otter", "beaver"):
        learner.post("/api/notebook/words", json={"word": word, "meaning_vi": "x"})
    ai.queue(suggest_answer("badger", "ferret", "mole"))
    body = suggest(learner).json()
    assert body["cached"] is False
    assert len(ai.calls) == 2


def test_bad_topic_and_level(learner, ai):
    assert suggest(learner, topic_id=999).status_code == 404
    assert suggest(learner, level="Z9").status_code == 422
    assert ai.calls == []


def test_counts_towards_the_limit(learner, ai, monkeypatch):
    monkeypatch.setenv("AI_LIMIT_PER_MINUTE", "1")
    ai.queue(suggest_answer("otter", "beaver", "hedgehog"))
    assert suggest(learner).status_code == 200
    assert suggest(learner, exclude=["otter"]).status_code == 429


def test_needs_login(anon):
    r = anon.post("/api/ai/suggest-words", json={"topic_id": 1, "level": "A1"})
    assert r.status_code == 401

# tests/test_notebook.py — "My notebook": every user's own words (/api/notebook).
from tests.conftest import register

RESILIENT = {
    "word": "resilient",
    "meaning_vi": "kiên cường, mau phục hồi",
    "ipa": "/rɪˈzɪliənt/",
    "part_of_speech": "adjective",
    "definition_en": "able to recover quickly from difficulties",
    "examples": [
        {"en": "Children are often very resilient.", "vi": "Trẻ em thường rất kiên cường."},
        {"en": "The city's economy proved resilient."},
    ],
    "synonyms": ["tough", "hardy", "Tough"],
    "antonyms": ["fragile"],
    "collocations": ["remarkably resilient"],
}


def test_learner_adds_a_word_with_every_field(learner):
    r = learner.post("/api/notebook/words", json=RESILIENT)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ipa"] == "/rɪˈzɪliənt/"
    assert body["examples"][1] == {"en": "The city's economy proved resilient.", "vi": None}
    # Duplicates in a list are dropped, ignoring case.
    assert body["synonyms"] == ["tough", "hardy"]
    assert body["source"] == "manual"
    assert body["bank_word_id"] is None


def test_only_word_and_meaning_are_required(learner):
    r = learner.post("/api/notebook/words", json={"word": "  cat ", "meaning_vi": "con mèo"})
    assert r.status_code == 201
    body = r.json()
    assert body["word"] == "cat"
    assert body["examples"] == [] and body["synonyms"] == []
    assert learner.post("/api/notebook/words", json={"word": "dog"}).status_code == 422
    blank = {"word": " ", "meaning_vi": "x"}
    assert learner.post("/api/notebook/words", json=blank).status_code == 422


def test_same_word_twice_is_rejected_in_one_notebook(learner):
    learner.post("/api/notebook/words", json=RESILIENT)
    r = learner.post("/api/notebook/words", json={**RESILIENT, "word": "Resilient"})
    assert r.status_code == 409


def test_notebooks_are_private(learner, new_browser):
    learner.post("/api/notebook/words", json=RESILIENT)
    other = new_browser()
    register(other, email="binh@example.com", name="Bình")
    assert other.get("/api/notebook/words").json() == []
    # The other user can save the same word in their own notebook...
    assert other.post("/api/notebook/words", json=RESILIENT).status_code == 201
    # ...but cannot read, change or delete someone else's.
    assert other.get("/api/notebook/words/1").status_code == 404
    assert other.patch("/api/notebook/words/1", json={"meaning_vi": "x"}).status_code == 404
    assert other.delete("/api/notebook/words/1").status_code == 404
    assert learner.get("/api/notebook/words/1").json()["meaning_vi"] == RESILIENT["meaning_vi"]


def test_notebook_needs_login(anon):
    assert anon.get("/api/notebook/words").status_code == 401
    assert anon.post("/api/notebook/words", json=RESILIENT).status_code == 401


def test_list_and_search(learner):
    learner.post("/api/notebook/words", json=RESILIENT)
    learner.post("/api/notebook/words", json={"word": "book", "meaning_vi": "quyển sách"})
    assert [w["word"] for w in learner.get("/api/notebook/words").json()] == ["book", "resilient"]
    found = learner.get("/api/notebook/words", params={"q": "kiên"}).json()
    assert [w["word"] for w in found] == ["resilient"]


def test_update_only_sent_fields(learner):
    learner.post("/api/notebook/words", json=RESILIENT)
    change = {"usage_note": "dùng cho người & vật", "antonyms": []}
    r = learner.patch("/api/notebook/words/1", json=change)
    assert r.status_code == 200
    body = r.json()
    assert body["usage_note"] == "dùng cho người & vật"
    assert body["antonyms"] == []
    assert body["synonyms"] == ["tough", "hardy"]
    # A null meaning is ignored instead of breaking the required column.
    assert learner.patch("/api/notebook/words/1", json={"meaning_vi": None}).json()["meaning_vi"]
    assert learner.patch("/api/notebook/words/1", json={"topic_id": 99}).status_code == 422


def test_delete(learner):
    learner.post("/api/notebook/words", json=RESILIENT)
    assert learner.delete("/api/notebook/words/1").status_code == 204
    assert learner.get("/api/notebook/words/1").status_code == 404


def test_copy_a_bank_word_into_my_notebook(client, learner):
    # client is an admin: it adds the word to the shared bank.
    client.post("/api/words", json={
        "word": "apple", "meaning_vi": "quả táo", "part_of_speech": "noun",
        "example": "I eat an apple.", "topic_id": 1,
    })
    r = learner.post("/api/notebook/from-bank/1")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "bank" and body["bank_word_id"] == 1
    assert body["examples"] == [{"en": "I eat an apple.", "vi": None}]
    assert body["topic_id"] == 1
    assert learner.post("/api/notebook/from-bank/1").status_code == 409
    assert learner.post("/api/notebook/from-bank/99").status_code == 404
    # The shared bank itself is unchanged and learners still cannot edit it.
    assert learner.patch("/api/words/1", json={"meaning_vi": "x"}).status_code == 403
    assert len(client.get("/api/words").json()) == 1

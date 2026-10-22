# tests/test_words.py — CRUD API for /api/words.
APPLE = {"word": "apple", "meaning_vi": "quả táo", "part_of_speech": "noun"}


def test_create_word(client):
    r = client.post("/api/words", json=APPLE)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["word"] == "apple"
    # No AI answer yet: example and usage_note stay empty for the user to fill in.
    assert body["example"] is None
    assert body["usage_note"] is None


def test_create_word_requires_word_and_meaning(client):
    assert client.post("/api/words", json={"word": "apple"}).status_code == 422
    assert client.post("/api/words", json={"word": "", "meaning_vi": "x"}).status_code == 422


def test_duplicate_word_is_rejected(client):
    client.post("/api/words", json=APPLE)
    r = client.post("/api/words", json={**APPLE, "word": "Apple"})
    assert r.status_code == 409


def test_list_and_search_words(client):
    client.post("/api/words", json=APPLE)
    client.post("/api/words", json={"word": "book", "meaning_vi": "quyển sách"})
    assert [w["word"] for w in client.get("/api/words").json()] == ["book", "apple"]
    assert [w["word"] for w in client.get("/api/words", params={"q": "sách"}).json()] == ["book"]


def test_get_word(client):
    client.post("/api/words", json=APPLE)
    assert client.get("/api/words/1").json()["meaning_vi"] == "quả táo"
    assert client.get("/api/words/99").status_code == 404


def test_update_only_sent_fields(client):
    client.post("/api/words", json=APPLE)
    r = client.patch("/api/words/1", json={"example": "I eat an apple every day."})
    assert r.status_code == 200
    body = r.json()
    assert body["example"] == "I eat an apple every day."
    assert body["meaning_vi"] == "quả táo"
    assert client.patch("/api/words/99", json={"example": "x"}).status_code == 404


def test_delete_word(client):
    client.post("/api/words", json=APPLE)
    assert client.delete("/api/words/1").status_code == 204
    assert client.get("/api/words/1").status_code == 404
    assert client.delete("/api/words/1").status_code == 404

# tests/test_reviews.py — review logs under /api/words/{id}/reviews.
def add_apple(client):
    return client.post("/api/words", json={"word": "apple", "meaning_vi": "quả táo"}).json()["id"]


def test_add_and_list_reviews(client):
    word_id = add_apple(client)
    r = client.post(f"/api/words/{word_id}/reviews", json={"result": "forgot"})
    assert r.status_code == 201
    client.post(f"/api/words/{word_id}/reviews", json={"result": "remembered"})
    results = [r["result"] for r in client.get(f"/api/words/{word_id}/reviews").json()]
    assert results == ["remembered", "forgot"]  # newest first


def test_review_result_must_be_valid(client):
    word_id = add_apple(client)
    r = client.post(f"/api/words/{word_id}/reviews", json={"result": "maybe"})
    assert r.status_code == 422


def test_review_unknown_word(client):
    assert client.post("/api/words/99/reviews", json={"result": "forgot"}).status_code == 404
    assert client.get("/api/words/99/reviews").status_code == 404


def test_deleting_word_deletes_reviews(client, repo):
    word_id = add_apple(client)
    client.post(f"/api/words/{word_id}/reviews", json={"result": "forgot"})
    client.delete(f"/api/words/{word_id}")
    assert repo.reviews == []

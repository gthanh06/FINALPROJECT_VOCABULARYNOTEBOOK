# tests/test_topics.py — words grouped by topic.
DOG = {"word": "dog", "meaning_vi": "con chó", "topic_id": 1}


def test_topics_list_counts_my_words(client):
    client.post("/api/words", json=DOG)
    client.post("/api/words", json={"word": "cat", "meaning_vi": "con mèo", "topic_id": 1})
    client.post("/api/words", json={"word": "sofa", "meaning_vi": "ghế sofa", "topic_id": 2})
    client.post("/api/words", json={"word": "hello", "meaning_vi": "xin chào"})  # no topic
    topics = client.get("/api/topics").json()
    assert [(t["slug"], t["word_count"]) for t in topics] == [("animals", 2), ("home", 1)]


def test_word_keeps_its_topic(client):
    word = client.post("/api/words", json=DOG).json()
    assert word["topic_id"] == 1
    assert client.get(f"/api/words/{word['id']}").json()["topic_id"] == 1


def test_topic_is_optional(client):
    assert client.post("/api/words", json={"word": "hi", "meaning_vi": "chào"}).json()[
        "topic_id"
    ] is None


def test_change_and_clear_topic(client):
    word_id = client.post("/api/words", json=DOG).json()["id"]
    assert client.patch(f"/api/words/{word_id}", json={"topic_id": 2}).json()["topic_id"] == 2
    assert client.patch(f"/api/words/{word_id}", json={"topic_id": None}).json()["topic_id"] is None


def test_unknown_topic_is_rejected(client):
    assert client.post("/api/words", json={**DOG, "topic_id": 99}).status_code == 422
    word_id = client.post("/api/words", json=DOG).json()["id"]
    assert client.patch(f"/api/words/{word_id}", json={"topic_id": 99}).status_code == 422


def test_topics_need_login(anon):
    assert anon.get("/api/topics").status_code == 401


def test_counts_are_per_user(anon):
    from tests.conftest import register

    register(anon, email="an@example.com")
    anon.post("/api/words", json=DOG)
    anon.post("/api/auth/logout")
    register(anon, email="binh@example.com", name="Bình")
    assert all(t["word_count"] == 0 for t in anon.get("/api/topics").json())

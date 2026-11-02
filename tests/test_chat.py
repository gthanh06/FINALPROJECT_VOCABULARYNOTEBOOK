# tests/test_chat.py — POST /api/ai/chat: a practice chat that uses my notebook words.
from tests.conftest import register
from tests.fake_ai import chat_answer


def add_words(browser, *words):
    ids = []
    for word, meaning in words:
        r = browser.post("/api/notebook/words", json={"word": word, "meaning_vi": meaning})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def chat(browser, word_ids, messages=()):
    return browser.post("/api/ai/chat", json={"word_ids": word_ids, "messages": list(messages)})


def says(text):
    return {"role": "learner", "text": text}


def tutor(text):
    return {"role": "tutor", "text": text}


def test_the_tutor_starts_with_my_words(learner, ai):
    ids = add_words(learner, ("reader", "người đọc"), ("reluctant", "miễn cưỡng"))
    ai.queue(chat_answer())
    r = chat(learner, ids)
    assert r.status_code == 200, r.text
    assert r.json()["reply"]["reply"] == "Do you like reading books?"
    prompt = ai.calls[0]["prompt"]
    assert "- reader: người đọc\n- reluctant: miễn cưỡng" in prompt
    assert "(no messages yet: start the conversation)" in prompt


def test_conversation_is_sent_and_used_words_are_checked(learner, ai):
    ids = add_words(learner, ("reader", "người đọc"))
    correction = {"original": "I is", "corrected": "I am", "explanation_vi": "Dùng 'am' với 'I'."}
    ai.queue(chat_answer(learner_used=["Reader", "banana", "reader"], correction=correction))
    r = chat(learner, ids, [tutor("Hi! Do you read?"), says("I is a  big reader.")])
    reply = r.json()["reply"]
    assert reply["learner_used"] == ["reader"]  # only target words, once
    assert reply["correction"]["corrected"] == "I am"
    assert "Tutor: Hi! Do you read?\nLearner: I is a big reader." in ai.calls[0]["prompt"]


def test_last_message_must_be_mine(learner, ai):
    ids = add_words(learner, ("reader", "người đọc"))
    assert chat(learner, ids, [says("hi"), tutor("hello")]).status_code == 422
    assert ai.calls == []


def test_only_my_own_words(learner, new_browser, ai):
    ids = add_words(learner, ("reader", "người đọc"))
    other = new_browser()
    register(other, email="binh@example.com", name="Bình")
    assert chat(other, ids).status_code == 404
    assert chat(learner, []).status_code == 422
    assert ai.calls == []


def test_long_chats_are_limited(learner, ai):
    ids = add_words(learner, ("reader", "người đọc"))
    too_many = [says("hi")] * 21
    assert chat(learner, ids, too_many).status_code == 422
    assert chat(learner, ids, [says("x" * 501)]).status_code == 422


def test_counts_towards_the_limit(learner, ai, monkeypatch):
    monkeypatch.setenv("AI_LIMIT_PER_MINUTE", "1")
    ids = add_words(learner, ("reader", "người đọc"))
    ai.queue(chat_answer())
    assert chat(learner, ids).status_code == 200
    assert chat(learner, ids, [says("hi")]).status_code == 429


def test_needs_login(anon):
    assert anon.post("/api/ai/chat", json={"word_ids": [1]}).status_code == 401

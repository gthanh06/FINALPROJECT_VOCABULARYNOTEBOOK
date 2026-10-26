# tests/test_grading.py — typed answers in both review directions.
import pytest

from app.grading import check, vi_answers

ADVANTAGE = {"word": "advantage", "meaning_vi": "lợi thế, ưu điểm"}
ENROLL = {"word": "enroll", "meaning_vi": "đăng ký (khoá học)"}
POLLUTION = {"word": "pollution", "meaning_vi": "sự ô nhiễm"}
LOOK = {"word": "look forward to", "meaning_vi": "mong chờ"}


@pytest.mark.parametrize(
    "word, answer, verdict",
    [
        (ADVANTAGE, "lợi thế", "correct"),
        (ADVANTAGE, "  Ưu Điểm. ", "correct"),  # any listed meaning, case and spaces ignored
        (ADVANTAGE, "loi the", "accent"),  # no accents still means the right word
        (ADVANTAGE, "lợi thê", "accent"),
        (ADVANTAGE, "lợi thết", "close"),  # one-letter typo
        (ADVANTAGE, "bất lợi", "wrong"),
        (ADVANTAGE, "", "wrong"),
        (ENROLL, "đăng ký", "correct"),  # the part in brackets is optional
        (ENROLL, "đăng ký khóa học", "correct"),  # new-style tone mark "khóa" = "khoá"
        (POLLUTION, "ô nhiễm", "correct"),  # "sự" is optional
    ],
)
def test_english_to_vietnamese(word, answer, verdict):
    assert check(word, "en-vi", answer)["verdict"] == verdict


def test_en_vi_counts_small_mistakes_as_correct():
    assert check(ADVANTAGE, "en-vi", "loi the")["correct"]
    assert check(ADVANTAGE, "en-vi", "lợi thết")["correct"]
    assert not check(ADVANTAGE, "en-vi", "bất lợi")["correct"]
    assert check(ADVANTAGE, "en-vi", "x")["expected"] == "lợi thế, ưu điểm"


@pytest.mark.parametrize(
    "word, answer, verdict, correct",
    [
        (ADVANTAGE, "Advantage", "correct", True),
        (ADVANTAGE, "advantge", "close", False),  # spelling matters in this direction
        (ADVANTAGE, "benefit", "wrong", False),
        (LOOK, "look  forward to", "correct", True),
        (LOOK, "look forward", "wrong", False),
    ],
)
def test_vietnamese_to_english(word, answer, verdict, correct):
    result = check(word, "vi-en", answer)
    assert (result["verdict"], result["correct"]) == (verdict, correct)
    assert result["expected"] == word["word"]


def test_vi_answers_lists_every_accepted_form():
    assert vi_answers("tiền thuê nhà; thuê") == {"tiền thuê nhà", "thuê"}


def test_check_endpoint(client):
    word_id = client.post("/api/words", json=ADVANTAGE).json()["id"]
    r = client.post(f"/api/words/{word_id}/check", json={"direction": "en-vi", "answer": "ưu điểm"})
    assert r.status_code == 200
    assert r.json() == {"verdict": "correct", "correct": True, "expected": "lợi thế, ưu điểm"}
    # Checking does not log a review; the page does that afterwards.
    assert client.get(f"/api/words/{word_id}/reviews").json() == []


def test_check_endpoint_validates(client, anon):
    word_id = client.post("/api/words", json=ADVANTAGE).json()["id"]
    bad = client.post(f"/api/words/{word_id}/check", json={"direction": "fr-en", "answer": "x"})
    assert bad.status_code == 422
    missing = client.post("/api/words/999/check", json={"direction": "en-vi", "answer": "x"})
    assert missing.status_code == 404

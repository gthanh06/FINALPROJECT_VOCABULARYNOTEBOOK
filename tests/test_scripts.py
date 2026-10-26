# tests/test_scripts.py — the offline parts of the word-list scripts (no download, no AI call).
from scripts import ai_enrich, build_wordlist

EMPTY = dict.fromkeys(ai_enrich.COLUMNS, "")


def test_clean_gloss_keeps_it_short():
    assert build_wordlist.clean_gloss("Đạt được, giành được.") == "đạt được, giành được"
    assert build_wordlist.clean_gloss("Một, hai, ba, bốn.") == "một, hai, ba"


def test_forms_find_inflections():
    assert {"studies", "studied", "study"} <= build_wordlist.forms("study")
    assert "making" in build_wordlist.forms("make")


def test_merge_only_fills_empty_cells():
    row = {**EMPTY, "word": "dog", "meaning_vi": "con chó", "topic": "animals", "source": "ngsl"}
    answer = {"meaning_vi": "chó", "example": "The dog barks.", "part_of_speech": "noun",
              "topic": "home"}
    out = ai_enrich.merge(row, answer, retopic=True)
    assert out["meaning_vi"] == "con chó"  # kept
    assert out["topic"] == "animals"  # kept: only "common" is re-sorted
    assert (out["example"], out["part_of_speech"]) == ("The dog barks.", "noun")
    assert out["source"] == "ngsl+ai"


def test_merge_ignores_invalid_values():
    row = {**EMPTY, "word": "dog", "topic": "common", "source": "ngsl"}
    out = ai_enrich.merge(row, {"part_of_speech": "animal", "topic": "pets"}, retopic=True)
    assert (out["part_of_speech"], out["topic"], out["source"]) == ("", "common", "ngsl")


def test_retopic_only_when_asked():
    row = {**EMPTY, "word": "dog", "meaning_vi": "chó", "example": "A dog.",
           "part_of_speech": "noun", "topic": "common"}
    assert not ai_enrich.needs_ai(row, retopic=False)
    assert ai_enrich.needs_ai(row, retopic=True)
    assert ai_enrich.merge(row, {"topic": "animals"}, retopic=False)["topic"] == "common"
    assert ai_enrich.merge(row, {"topic": "animals"}, retopic=True)["topic"] == "animals"


def test_new_ai_word_is_marked_once():
    row = {**EMPTY, "word": "owl", "topic": "animals", "source": "ai"}
    assert ai_enrich.merge(row, {"meaning_vi": "con cú"}, retopic=False)["source"] == "ai"

# app/grading.py — checks a typed review answer against the saved word.
#
#   en-vi: the app shows the English word, the learner types the Vietnamese meaning.
#          Any of the listed meanings counts ("lợi thế, ưu điểm"), missing accents and
#          a one-letter typo still count, so the learner is graded on meaning, not typing.
#   vi-en: the app shows the meaning, the learner types the English word.
#          Spelling is the point here, so a one-letter typo is "close" but not correct.
import re
import unicodedata

# Verdicts, from best to worst.
CORRECT = "correct"  # matches exactly (ignoring case, spaces, punctuation)
ACCENT = "accent"  # right word, wrong or missing Vietnamese accents
CLOSE = "close"  # a small typo
WRONG = "wrong"

# Old and new tone-mark placement are both standard Vietnamese ("hoà" / "hòa").
TONE_PLACEMENT = {
    "oá": "óa", "oà": "òa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oé": "óe", "oè": "òe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uý": "úy", "uỳ": "ùy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}
TONE_RE = re.compile("(" + "|".join(TONE_PLACEMENT) + r")(?!\w)")

# "sự ô nhiễm" is also answered as "ô nhiễm".
VI_PREFIXES = ("sự ", "việc ", "một cách ", "cái ")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = TONE_RE.sub(lambda m: TONE_PLACEMENT[m.group(1)], text)
    text = re.sub(r"[^\w\s'-]", " ", text)
    return " ".join(text.split())


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def vi_answers(meaning: str) -> set[str]:
    """Every accepted way to write a Vietnamese meaning."""
    answers = set()
    for part in re.split(r"[,;/]", meaning):
        without_brackets = re.sub(r"\(.*?\)", " ", part)
        for variant in (part, without_brackets):
            v = normalize(variant)
            if not v:
                continue
            answers.add(v)
            for prefix in VI_PREFIXES:
                if v.startswith(prefix):
                    answers.add(v[len(prefix):])
    return answers


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def typos_allowed(length: int) -> int:
    return 0 if length < 4 else 1 if length < 9 else 2


def grade(answer: str, accepted: set[str]) -> str:
    a = normalize(answer)
    if not a:
        return WRONG
    if a in accepted:
        return CORRECT
    bare = strip_accents(a)
    bare_accepted = {strip_accents(x) for x in accepted}
    if bare in bare_accepted:
        return ACCENT
    if any(levenshtein(bare, x) <= typos_allowed(len(x)) for x in bare_accepted):
        return CLOSE
    return WRONG


def check(word: dict, direction: str, answer: str) -> dict:
    if direction == "en-vi":
        verdict = grade(answer, vi_answers(word["meaning_vi"]))
        expected = word["meaning_vi"]
        correct = verdict in (CORRECT, ACCENT, CLOSE)
    else:
        verdict = grade(answer, {normalize(word["word"])})
        expected = word["word"]
        correct = verdict in (CORRECT, ACCENT)
    return {"verdict": verdict, "correct": correct, "expected": expected}

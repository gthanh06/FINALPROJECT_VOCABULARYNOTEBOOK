# scripts/build_wordlist.py — build a word-bank CSV from open data, ready for Admin → Import CSV.
#
#   python scripts/build_wordlist.py --count 1000 --exclude current.csv --out data/ngsl_1000.csv
#
# Sources (downloaded once into scripts/.cache/, see data/README.md for the licenses):
#   word list      NGSL 1.2, words ranked by how common they are          CC BY-SA 4.0
#   meaning_vi     Vietnamese Wiktionary, English entries (kaikki.org)    CC BY-SA
#   example        Tatoeba English sentences that have a Vietnamese pair  CC BY 2.0 FR
# Words with no Vietnamese meaning are skipped unless --keep-missing is given
# (then scripts/ai_enrich.py can fill them). Standard library only.
import argparse
import bz2
import csv
import json
import re
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache"
SOURCES = {
    "ngsl.csv": "https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv",
    "en_vi.jsonl": "https://kaikki.org/viwiktionary/Ti%E1%BA%BFng%20Anh/kaikki.org-dictionary-Ti%E1%BA%BFngAnh.jsonl",
    "vie_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/vie/vie_sentences.tsv.bz2",
    "vie-eng_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/vie/vie-eng_links.tsv.bz2",
    "eng_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
}
COLUMNS = ("word", "meaning_vi", "part_of_speech", "example", "usage_note", "topic", "source")

# Grammar words: too basic for a vocabulary notebook.
STOPWORDS = set("""
a an the and or but nor so yet if than that this these those there here
i me my mine myself you your yours yourself he him his himself she her hers herself
it its itself we us our ours ourselves they them their theirs themselves
who whom whose which what where when why how whether
be am is are was were been being have has had having do does did done
will would shall should can could may might must ought
of to in on at by for from with about as into onto upon over under up down out off
not no yes all any some each every both either neither such own same other another
one two three four five six seven eight nine ten
""".split())

POS = {
    "noun": "noun", "name": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb",
    "prep": "preposition", "conj": "conjunction", "pron": "pronoun", "phrase": "phrase",
}
# Senses that only point at another word ("plural of ...", "past tense of ...").
SKIP_GLOSS = re.compile(r"^(số nhiều|quá khứ|phân từ|dạng|viết tắt|xem|như|thì)\b", re.I)


def download(name: str) -> Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(SOURCES[name], path)
    return path


def ngsl_ranked() -> list[str]:
    with open(download("ngsl.csv"), encoding="utf-8-sig") as f:
        return [row["Lemma"].strip().lower() for row in csv.DictReader(f) if row["Lemma"].strip()]


def clean_gloss(gloss: str) -> str:
    gloss = gloss.strip().rstrip(".").strip()
    parts = [p.strip() for p in gloss.split(",") if p.strip()]
    # Keep it short enough to type in Practice: at most three meanings.
    gloss = ", ".join(parts[:3])
    return gloss[:1].lower() + gloss[1:]


def wiktionary(words: set[str]) -> dict[str, dict]:
    """word -> {meaning_vi, part_of_speech, usage_note}, from the entry with the most senses."""
    best: dict[str, tuple[int, dict]] = {}
    with open(download("en_vi.jsonl"), encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("word", "").strip().lower()
            if word not in words:
                continue
            senses = [
                s for s in entry.get("senses", [])
                if s.get("glosses") and not SKIP_GLOSS.match(s["glosses"][0])
            ]
            if not senses or len(senses) <= best.get(word, (0, None))[0]:
                continue
            note = None
            for s in senses:
                for ex in s.get("examples", []):
                    text, vi = ex.get("text", "").strip(), ex.get("translation", "").strip()
                    if text and vi and len(text) + len(vi) <= 70:
                        note = f"{text} = {vi}"
                        break
                if note:
                    break
            best[word] = (len(senses), {
                "meaning_vi": clean_gloss(senses[0]["glosses"][0]),
                "part_of_speech": POS.get(entry.get("pos", "")),
                "usage_note": note,
            })
    return {w: data for w, (_, data) in best.items()}


def forms(word: str) -> set[str]:
    """The word and its regular inflections, to find it inside a sentence."""
    out = {word, word + "s", word + "es", word + "ed", word + "d", word + "ing", word + "er"}
    if word.endswith("e"):
        out.add(word[:-1] + "ing")
    if word.endswith("y"):
        out |= {word[:-1] + "ies", word[:-1] + "ied"}
    return out


def tatoeba_examples(words: list[str]) -> dict[str, str]:
    """word -> a short English sentence that has a Vietnamese translation on Tatoeba."""
    def read(name):
        with bz2.open(download(name), "rt", encoding="utf-8") as f:
            return [line.rstrip("\n").split("\t") for line in f]

    eng_ids = {int(eng) for _vie, eng in read("vie-eng_links.tsv.bz2")}
    sentences = [
        text for sid, _lang, text in read("eng_sentences.tsv.bz2") if int(sid) in eng_ids
    ]
    by_token: dict[str, list[str]] = {}
    for text in sentences:
        n = len(text.split())
        if 4 <= n <= 12:
            for token in set(re.findall(r"[a-z']+", text.lower())):
                by_token.setdefault(token, []).append(text)
    found = {}
    for word in words:
        if " " in word:
            continue
        candidates = [t for f in forms(word) for t in by_token.get(f, [])]
        if candidates:
            # The shortest sentence is usually the clearest example.
            found[word] = min(candidates, key=lambda t: (len(t), t))
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--out", default="data/ngsl_1000.csv")
    ap.add_argument("--exclude", help="CSV with a 'word' column (e.g. Admin → Export CSV)")
    ap.add_argument("--overrides", default="data/review_overrides.csv",
                    help="CSV word,meaning_vi,part_of_speech,topic: reviewed fixes; empty cells"
                         " keep the value from the sources (default topic: common)")
    ap.add_argument("--keep-missing", action="store_true",
                    help="keep words with no Vietnamese meaning (fill them with ai_enrich.py)")
    args = ap.parse_args()

    exclude = set()
    if args.exclude:
        with open(args.exclude, encoding="utf-8-sig") as f:
            exclude = {row["word"].strip().lower() for row in csv.DictReader(f)}
    overrides = {}
    if args.overrides and Path(args.overrides).exists():
        with open(args.overrides, encoding="utf-8-sig") as f:
            overrides = {row["word"].strip().lower(): row for row in csv.DictReader(f)}

    ranked = [w for w in ngsl_ranked() if w not in STOPWORDS and w not in exclude]
    meanings = wiktionary(set(ranked))
    picked = [w for w in ranked if w in meanings or args.keep_missing][: args.count]
    examples = tatoeba_examples(picked)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for word in picked:
            m = meanings.get(word, {})
            fix = overrides.get(word, {})
            row = {
                "word": word,
                "meaning_vi": m.get("meaning_vi", ""),
                "part_of_speech": m.get("part_of_speech") or "",
                "example": examples.get(word, ""),
                "usage_note": m.get("usage_note") or "",
                "topic": "common",
                "source": "ngsl+wiktionary" + ("+tatoeba" if word in examples else ""),
            }
            if (fix.get("meaning_vi") or "").strip():
                row["meaning_vi"] = fix["meaning_vi"].strip()
                # The Wiktionary note was about the sense we just replaced.
                row["usage_note"] = ""
                row["source"] += "+reviewed"
            for col in ("part_of_speech", "topic"):
                if (fix.get(col) or "").strip():
                    row[col] = fix[col].strip()
            writer.writerow(row)
    with_example = sum(w in examples for w in picked)
    print(f"wrote {len(picked)} words to {out} ({with_example} with an example sentence)")


if __name__ == "__main__":
    main()

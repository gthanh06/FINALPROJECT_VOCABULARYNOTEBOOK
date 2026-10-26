# app/importer.py — CSV import / export of the word bank (admin page).
#
# File format (UTF-8, first line is the header, Excel's "CSV UTF-8" works):
#   word,meaning_vi,part_of_speech,example,usage_note,topic
# word and meaning_vi are required. topic is a topic slug ("animals") or its name
# ("Animals"); empty means "Uncategorized". part_of_speech also accepts short forms
# such as "n", "v", "adj".
import csv
import io

COLUMNS = ("word", "meaning_vi", "part_of_speech", "example", "usage_note", "topic")
REQUIRED = ("word", "meaning_vi")
MAX_ROWS = 5000
MAX_WORD = 100

POS_ALIASES = {
    "noun": "noun", "n": "noun",
    "verb": "verb", "v": "verb",
    "adjective": "adjective", "adj": "adjective",
    "adverb": "adverb", "adv": "adverb",
    "preposition": "preposition", "prep": "preposition",
    "conjunction": "conjunction", "conj": "conjunction",
    "pronoun": "pronoun", "pron": "pronoun",
    "phrase": "phrase",
}


class BadCsv(Exception):
    """The file cannot be read at all (wrong header, too many rows)."""


def parse(text: str, topics: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (rows ready to save, errors as {"line", "message"}). Lines count from 1."""
    topic_ids = {}
    for t in topics:
        topic_ids[t["slug"].lower()] = t["id"]
        topic_ids[t["name"].lower()] = t["id"]

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise BadCsv(
            "The first line must be the header: " + ",".join(COLUMNS)
            + f" (missing: {', '.join(missing)})"
        )
    reader.fieldnames = header

    rows, errors, seen = [], [], {}
    for line, raw in enumerate(reader, start=2):
        if len(rows) + len(errors) >= MAX_ROWS:
            raise BadCsv(f"Too many rows: at most {MAX_ROWS} per file")
        cell = {c: (raw.get(c) or "").strip() for c in COLUMNS}
        if not any(cell.values()):
            continue  # blank line

        problems = []
        if not cell["word"]:
            problems.append("word is empty")
        elif len(cell["word"]) > MAX_WORD:
            problems.append(f"word is longer than {MAX_WORD} characters")
        if not cell["meaning_vi"]:
            problems.append("meaning_vi is empty")
        pos = POS_ALIASES.get(cell["part_of_speech"].lower()) if cell["part_of_speech"] else None
        if cell["part_of_speech"] and pos is None:
            problems.append(f'unknown part_of_speech "{cell["part_of_speech"]}"')
        topic_id = topic_ids.get(cell["topic"].lower()) if cell["topic"] else None
        if cell["topic"] and topic_id is None:
            problems.append(f'unknown topic "{cell["topic"]}"')
        key = cell["word"].lower()
        if key and key in seen:
            problems.append(f'"{cell["word"]}" is already on line {seen[key]}')

        if problems:
            errors.append({"line": line, "message": "; ".join(problems)})
            continue
        seen[key] = line
        rows.append({
            "word": cell["word"],
            "meaning_vi": cell["meaning_vi"],
            "part_of_speech": pos,
            "example": cell["example"] or None,
            "usage_note": cell["usage_note"] or None,
            "topic_id": topic_id,
        })
    return rows, errors


def to_csv(words: list[dict], topics: list[dict]) -> str:
    """The whole word bank in the same format the import reads."""
    slugs = {t["id"]: t["slug"] for t in topics}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for w in sorted(words, key=lambda w: w["word"].lower()):
        writer.writerow([
            w["word"], w["meaning_vi"], w.get("part_of_speech") or "", w.get("example") or "",
            w.get("usage_note") or "", slugs.get(w.get("topic_id"), ""),
        ])
    # The BOM makes Excel open the file as UTF-8, so Vietnamese accents show correctly.
    return "\ufeff" + out.getvalue()

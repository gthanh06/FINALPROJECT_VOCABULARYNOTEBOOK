# scripts/ai_enrich.py — let an AI (Gemini) fill the gaps in a word-bank CSV, or add new words.
#
#   export GEMINI_API_KEY=...            # never commit it
#   python scripts/ai_enrich.py fill data/ngsl_1000.csv --out data/ngsl_1000_ai.csv
#   python scripts/ai_enrich.py fill data/ngsl_1000.csv --retopic     # also re-sort "common" words
#   python scripts/ai_enrich.py generate --topic animals --count 30 --out data/animals_ai.csv
#
# "fill" only writes into EMPTY cells (missing meaning / example / topic); what the sources
# or a person already wrote is never overwritten. Every row the AI touched gets "+ai" in the
# source column, so the team knows which rows to read before importing them on the Admin page.
# Standard library only; the model can be changed with GEMINI_MODEL.
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

COLUMNS = ("word", "meaning_vi", "part_of_speech", "example", "usage_note", "topic", "source")
TOPICS = (
    "study", "work", "technology", "daily", "home", "animals", "food", "travel", "health",
    "environment", "feelings", "common", "academic", "idioms",
)
POS = ("noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun", "phrase")
BATCH = 40
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

FILL_PROMPT = """You help build an English-Vietnamese vocabulary notebook for Vietnamese learners.
For each JSON object below, fill ONLY the fields that are empty strings:
- meaning_vi: the most common Vietnamese meaning, short (at most 3 meanings separated by "; ").
- part_of_speech: one of {pos}.
- example: one simple, natural English sentence (4-12 words) using the word in that meaning.
- topic: one of {topics}. Use "common" when no specific topic fits.
Keep non-empty fields exactly as they are. Answer with a JSON array of objects with the keys
word, meaning_vi, part_of_speech, example, topic, in the same order as the input.

{rows}"""

GENERATE_PROMPT = """You help build an English-Vietnamese vocabulary notebook.
Suggest {count} useful English words or short phrases for the topic "{topic}", for intermediate
learners. Do not include any of these existing words: {existing}.
Answer with a JSON array of objects with the keys word, meaning_vi (short, most common Vietnamese
meaning), part_of_speech (one of {pos}), example (one simple English sentence, 4-12 words) and
usage_note (a short collocation or tip, may be empty)."""


def needs_ai(row: dict, retopic: bool) -> bool:
    if not row["meaning_vi"] or not row["example"] or not row["part_of_speech"]:
        return True
    return retopic and row["topic"] in ("", "common")


def merge(row: dict, answer: dict, retopic: bool) -> dict:
    """Fill the empty cells of row from the AI answer; invalid values are ignored."""
    out = dict(row)
    changed = False
    for col in ("meaning_vi", "example"):
        value = str(answer.get(col) or "").strip()
        if not out[col] and value:
            out[col], changed = value, True
    pos = str(answer.get("part_of_speech") or "").strip().lower()
    if not out["part_of_speech"] and pos in POS:
        out["part_of_speech"], changed = pos, True
    topic = str(answer.get("topic") or "").strip().lower()
    if topic in TOPICS and (not out["topic"] or (retopic and out["topic"] == "common")):
        if topic != out["topic"]:
            out["topic"], changed = topic, True
    if changed and "ai" not in out["source"].split("+"):
        out["source"] = (out["source"] + "+ai").lstrip("+")
    return out


def ask_gemini(prompt: str, api_key: str, model: str, retries: int = 5) -> list:
    """One request; retries on 429 / 5xx / timeout / empty answer with a growing pause."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }).encode()
    request = urllib.request.Request(
        API.format(model=model), data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    delay = 5
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as res:
                data = json.load(res)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            answer = json.loads(text)
            if isinstance(answer, list) and answer:
                return answer
            reason = "empty answer"
        except urllib.error.HTTPError as err:
            if err.code != 429 and err.code < 500:
                sys.exit(f"Gemini refused the request ({err.code}): {err.read()[:300]!r}")
            reason = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as err:
            reason = type(err).__name__
        print(f"  attempt {attempt}/{retries} failed ({reason}), waiting {delay}s")
        time.sleep(delay)
        delay *= 2
    sys.exit("Gemini did not answer; nothing was written. Try again later.")


def read_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [{c: (r.get(c) or "").strip() for c in COLUMNS} for r in csv.DictReader(f)]


def write_rows(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    fill = sub.add_parser("fill", help="fill empty cells of an existing CSV")
    fill.add_argument("csv")
    fill.add_argument("--out")
    fill.add_argument("--retopic", action="store_true", help='also re-sort words in "common"')
    gen = sub.add_parser("generate", help="suggest new words for one topic")
    gen.add_argument("--topic", required=True, choices=TOPICS)
    gen.add_argument("--count", type=int, default=30)
    gen.add_argument("--exclude", help="CSV whose words must not be suggested again")
    gen.add_argument("--out", required=True)
    for p in (fill, gen):
        p.add_argument("--dry-run", action="store_true", help="print the prompt, call nothing")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key and not args.dry_run:
        sys.exit("Set GEMINI_API_KEY first (or use --dry-run).")

    if args.cmd == "fill":
        rows = read_rows(args.csv)
        todo = [i for i, r in enumerate(rows) if needs_ai(r, args.retopic)]
        print(f"{len(todo)} of {len(rows)} rows need the AI, in {-(-len(todo) // BATCH)} requests")
        for start in range(0, len(todo), BATCH):
            batch = todo[start:start + BATCH]
            keys = ("word", "meaning_vi", "part_of_speech", "example", "topic")
            payload = [{k: rows[i][k] for k in keys} for i in batch]
            prompt = FILL_PROMPT.format(
                pos=", ".join(POS), topics=", ".join(TOPICS),
                rows=json.dumps(payload, ensure_ascii=False, indent=0),
            )
            if args.dry_run:
                print(prompt[:600], "...\n")
                break
            reply = ask_gemini(prompt, api_key, model)
            answers = {str(a.get("word", "")).lower(): a for a in reply}
            for i in batch:
                rows[i] = merge(rows[i], answers.get(rows[i]["word"].lower(), {}), args.retopic)
            print(f"  {min(start + BATCH, len(todo))}/{len(todo)} done")
        if not args.dry_run:
            write_rows(args.out or args.csv, rows)
    else:
        existing = set()
        if args.exclude:
            existing = {r["word"].lower() for r in read_rows(args.exclude)}
        prompt = GENERATE_PROMPT.format(
            count=args.count, topic=args.topic, pos=", ".join(POS),
            existing=", ".join(sorted(existing)[:400]) or "(none)",
        )
        if args.dry_run:
            print(prompt[:1200])
            return
        rows, seen = [], set(existing)
        for a in ask_gemini(prompt, api_key, model):
            word = str(a.get("word", "")).strip()
            if not word or word.lower() in seen or not str(a.get("meaning_vi", "")).strip():
                continue
            seen.add(word.lower())
            empty = {c: "" for c in COLUMNS}
            row = merge({**empty, "word": word, "topic": args.topic, "source": "ai"}, a, False)
            row["usage_note"] = str(a.get("usage_note") or "").strip()
            rows.append(row)
        write_rows(args.out, rows)


if __name__ == "__main__":
    main()

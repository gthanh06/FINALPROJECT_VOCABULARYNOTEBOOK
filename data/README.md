# data/ — word lists to import on the Admin page

| File | What it is |
|---|---|
| `ngsl_1000.csv` | 1000 common English words not yet in the starter bank, ready for **Admin → Import CSV** |
| `review_overrides.csv` | Reviewed fixes applied on top of the sources: Vietnamese meaning, part of speech, topic |

## How `ngsl_1000.csv` is made

```bash
# 1. Export the current bank (Admin → Export CSV) so its words are skipped, then:
python scripts/build_wordlist.py --count 1000 --exclude vocabulary.csv --out data/ngsl_1000.csv
# 2. (optional) let Gemini fill the empty cells / re-sort "common" words:
GEMINI_API_KEY=... python scripts/ai_enrich.py fill data/ngsl_1000.csv --out data/ngsl_1000_ai.csv
# 3. Read the rows marked +reviewed / +ai, then Admin → Import CSV.
```

1. **Word list**: the most frequent words of NGSL 1.2, skipping grammar words (the, of, will...)
   and the words already in the bank.
2. **Vietnamese meaning, part of speech, usage note**: the English entry with the most senses in
   the Vietnamese Wiktionary. That dictionary often lists an old or rare sense first
   (`summer` = "cái rầm", `test` = "vỏ tôm"), so...
3. **Review**: about 500 of the 1000 meanings were checked and replaced with the common sense in
   `review_overrides.csv` (AI-assisted, then read by a person); these rows have `+reviewed` in the
   `source` column and their Wiktionary usage note is dropped. The same file sets the topic;
   everything else is in `common`.
4. **Example sentence**: the shortest Tatoeba English sentence (4–12 words) containing the word,
   taken only from sentences that have a Vietnamese translation, i.e. simple everyday English.

The `source` column tells where each row comes from; the import ignores it.

## Sources and licenses

- **NGSL 1.2** (New General Service List), Browne, C., Culligan, B. & Phillips, J.,
  https://www.newgeneralservicelist.com — CC BY-SA 4.0
- **Wiktionary tiếng Việt**, English entries, via https://kaikki.org/viwiktionary/ (wiktextract)
  — CC BY-SA 4.0
- **Tatoeba**, https://tatoeba.org — CC BY 2.0 FR

Because two sources are CC BY-SA, `ngsl_1000.csv` is shared under **CC BY-SA 4.0** too.

-- 001_create_words.sql : one row per English word in the notebook.
-- example and usage_note may be NULL: the AI fills them, or the user types them
-- when the AI is busy (429 / timeout / empty answer).
CREATE TABLE IF NOT EXISTS words (
  id             serial PRIMARY KEY,
  word           text NOT NULL CHECK (length(trim(word)) > 0),
  meaning_vi     text NOT NULL,
  part_of_speech text,
  example        text,
  usage_note     text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- The same word cannot be saved twice ("Apple" and "apple" count as the same).
CREATE UNIQUE INDEX IF NOT EXISTS words_word_lower_key ON words (lower(word));

-- 008_user_words.sql : a private notebook for every user, next to the shared word bank.
-- The shared bank (words) and its practice history (review_logs) are not touched.
-- A learner adds words here by hand, copies them from the bank, or (later) lets the AI fill them.
CREATE TABLE IF NOT EXISTS user_words (
  id             serial PRIMARY KEY,
  user_id        integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  word           text NOT NULL CHECK (length(trim(word)) > 0),
  meaning_vi     text NOT NULL CHECK (length(trim(meaning_vi)) > 0),
  ipa            text,
  part_of_speech text,
  definition_en  text,
  -- [{"en": "...", "vi": "..."}]: example sentences with their Vietnamese translation.
  examples       jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(examples) = 'array'),
  synonyms       text[] NOT NULL DEFAULT '{}',
  antonyms       text[] NOT NULL DEFAULT '{}',
  collocations   text[] NOT NULL DEFAULT '{}',
  usage_note     text,
  topic_id       integer REFERENCES topics (id) ON DELETE SET NULL,
  -- manual = typed by the user, bank = copied from the shared bank, ai = filled by the AI.
  source         text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'bank', 'ai')),
  -- The bank word it was copied from; the copy stays if the bank word is deleted.
  bank_word_id   integer REFERENCES words (id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

-- A word is saved once per notebook ("Apple" and "apple" count as the same).
CREATE UNIQUE INDEX IF NOT EXISTS user_words_user_word_lower_key ON user_words (user_id, lower(word));

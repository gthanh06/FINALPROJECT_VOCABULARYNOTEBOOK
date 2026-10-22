-- 002_create_review_logs.sql : one row each time the user reviews a word.
-- Deleting a word deletes its review history too (ON DELETE CASCADE).
CREATE TABLE IF NOT EXISTS review_logs (
  id          serial PRIMARY KEY,
  word_id     integer NOT NULL REFERENCES words (id) ON DELETE CASCADE,
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  result      text NOT NULL CHECK (result IN ('remembered', 'forgot'))
);

CREATE INDEX IF NOT EXISTS review_logs_word_id_idx ON review_logs (word_id);

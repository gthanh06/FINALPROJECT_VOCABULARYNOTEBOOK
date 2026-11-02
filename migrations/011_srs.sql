-- 011_srs.sql : spaced-repetition state and per-user review history.
ALTER TABLE user_words
  ADD COLUMN IF NOT EXISTS srs_level smallint NOT NULL DEFAULT 0
    CHECK (srs_level BETWEEN 0 AND 5),
  ADD COLUMN IF NOT EXISTS srs_ease numeric(4, 2) NOT NULL DEFAULT 2.50
    CHECK (srs_ease >= 1.30),
  ADD COLUMN IF NOT EXISTS srs_interval integer NOT NULL DEFAULT 0
    CHECK (srs_interval >= 0),
  ADD COLUMN IF NOT EXISTS next_review date;

CREATE INDEX IF NOT EXISTS user_words_due_idx ON user_words (user_id, next_review);

CREATE TABLE IF NOT EXISTS srs_reviews (
  id            bigserial PRIMARY KEY,
  user_id       integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  word_id       integer NOT NULL REFERENCES user_words (id) ON DELETE CASCADE,
  quality       smallint NOT NULL CHECK (quality BETWEEN 0 AND 5),
  level         smallint NOT NULL CHECK (level BETWEEN 0 AND 5),
  ease          numeric(4, 2) NOT NULL CHECK (ease >= 1.30),
  interval_days integer NOT NULL CHECK (interval_days >= 1),
  next_review   date NOT NULL,
  reviewed_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS srs_reviews_user_time_idx ON srs_reviews (user_id, reviewed_at DESC);

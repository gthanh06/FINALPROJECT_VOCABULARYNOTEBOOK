-- 004_users_and_sessions.sql : accounts, login sessions, and one notebook per user.
CREATE TABLE IF NOT EXISTS users (
  id            serial PRIMARY KEY,
  email         text NOT NULL,
  display_name  text NOT NULL CHECK (length(trim(display_name)) > 0),
  password_hash text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- One account per email ("A@x.com" and "a@x.com" count as the same).
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key ON users (lower(email));

-- The browser keeps a random token in an HttpOnly cookie; only its SHA-256 is stored,
-- so a leaked database cannot be used to log in. Logging out deletes the row.
CREATE TABLE IF NOT EXISTS sessions (
  token_hash text PRIMARY KEY,
  user_id    integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions (user_id);

-- Every word now belongs to a user. Words with user_id NULL (the seeded set from 003)
-- are the starter notebook copied to each new account when it registers.
ALTER TABLE words ADD COLUMN IF NOT EXISTS user_id integer REFERENCES users (id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS words_user_id_idx ON words (user_id);

-- A word is unique inside one notebook, not across all users.
DROP INDEX IF EXISTS words_word_lower_key;
CREATE UNIQUE INDEX IF NOT EXISTS words_user_word_lower_key
  ON words (user_id, lower(word)) NULLS NOT DISTINCT;

-- 010_quizzes.sql : server-side quiz sessions for a user's private notebook.
CREATE TABLE IF NOT EXISTS quizzes (
  id           bigserial PRIMARY KEY,
  user_id      integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  questions    jsonb NOT NULL CHECK (jsonb_typeof(questions) = 'array'),
  result       jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
  created_at   timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz
);

CREATE INDEX IF NOT EXISTS quizzes_user_created_idx ON quizzes (user_id, created_at DESC);

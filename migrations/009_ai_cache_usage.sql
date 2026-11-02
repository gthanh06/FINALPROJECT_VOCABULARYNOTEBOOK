-- 009_ai_cache_usage.sql : AI answers kept for reuse, and how many AI calls each user made.

-- One answer per (kind, key): e.g. ('lookup', 'resilient'). The answer is the same for
-- every user, so a word looked up once never costs another AI call.
-- prompt_version: answers made with an older prompt (prompts/*.md) are redone.
CREATE TABLE IF NOT EXISTS ai_cache (
  kind           text NOT NULL,
  key            text NOT NULL,
  prompt_version text NOT NULL,
  model          text NOT NULL,
  data           jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, key)
);

-- One row per AI call that really went to the provider (cache hits are not counted).
-- Used for the per-user limits (AI_LIMIT_PER_MINUTE / AI_LIMIT_PER_DAY).
CREATE TABLE IF NOT EXISTS ai_usage (
  id         bigserial PRIMARY KEY,
  user_id    integer NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  feature    text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_usage_user_time_idx ON ai_usage (user_id, created_at);

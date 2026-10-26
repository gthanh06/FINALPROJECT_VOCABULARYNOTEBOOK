-- 007_admin_shared_words.sql : one shared word bank managed by admins.
-- Learners can no longer add words; they all study the same words, and each
-- learner keeps their own practice history (review_logs.user_id).

ALTER TABLE users ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'learner'
  CHECK (role IN ('learner', 'admin'));

ALTER TABLE review_logs ADD COLUMN IF NOT EXISTS user_id integer REFERENCES users (id) ON DELETE CASCADE;

-- Until now every learner had a private copy of each word. Move their practice
-- history from their copy onto the shared word with the same spelling...
UPDATE review_logs r
SET user_id = mine.user_id, word_id = shared.id
FROM words mine
JOIN words shared ON shared.user_id IS NULL AND lower(shared.word) = lower(mine.word)
WHERE r.word_id = mine.id AND mine.user_id IS NOT NULL;

-- ...then drop the private copies. A word only one learner had added goes too,
-- together with its history (ON DELETE CASCADE).
DELETE FROM words WHERE user_id IS NOT NULL;

-- Practice logged before accounts existed has no owner.
DELETE FROM review_logs WHERE user_id IS NULL;
ALTER TABLE review_logs ALTER COLUMN user_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS review_logs_user_word_idx ON review_logs (user_id, word_id);

-- Words no longer belong to a user: unique by spelling across the whole bank.
DROP INDEX IF EXISTS words_user_word_lower_key;
ALTER TABLE words DROP COLUMN IF EXISTS user_id;
CREATE UNIQUE INDEX IF NOT EXISTS words_word_lower_key ON words (lower(word));

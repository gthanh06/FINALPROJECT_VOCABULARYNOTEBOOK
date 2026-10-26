-- 006_topic_names_en.sql : the web UI is in English, so the topic names are too.
-- Slugs (used in URLs and code) do not change.
UPDATE topics SET name = v.name
FROM (VALUES
  ('study', 'Study & school'),
  ('work', 'Work'),
  ('technology', 'Technology'),
  ('daily', 'Daily life'),
  ('home', 'Home & furniture'),
  ('animals', 'Animals'),
  ('food', 'Food & drinks'),
  ('travel', 'Travel'),
  ('health', 'Health'),
  ('environment', 'Environment'),
  ('feelings', 'Feelings & personality'),
  ('common', 'Common words'),
  ('academic', 'Academic & IELTS'),
  ('idioms', 'Phrases & idioms')
) AS v (slug, name)
WHERE topics.slug = v.slug;

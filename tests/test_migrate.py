# tests/test_migrate.py — migrations are applied in order and only once.
from app.migrate import MIGRATIONS_DIR, pending


def test_migrations_run_in_name_order():
    names = [p.name for p in pending(set())]
    assert names == sorted(names)
    assert names[:2] == ["001_create_words.sql", "002_create_review_logs.sql"]


def test_applied_migrations_are_skipped():
    assert "001_create_words.sql" not in [p.name for p in pending({"001_create_words.sql"})]


def test_review_logs_reference_words():
    sql = (MIGRATIONS_DIR / "002_create_review_logs.sql").read_text(encoding="utf-8")
    assert "REFERENCES words (id) ON DELETE CASCADE" in sql

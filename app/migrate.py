# app/migrate.py — apply migrations/*.sql in name order, each one only once.
#
# Run it against whatever DATABASE_URL points at:
#   python -m app.migrate
# Applied files are recorded in the schema_migrations table, so running it
# again is safe and only applies the new files.
from pathlib import Path

from app.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def pending(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]


def migrate() -> list[str]:
    done = []
    with connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in pending(applied):
            # One transaction per file: a broken migration leaves no half-applied schema.
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            done.append(path.name)
    return done


if __name__ == "__main__":
    names = migrate()
    print("applied:", ", ".join(names) if names else "nothing, schema is up to date")

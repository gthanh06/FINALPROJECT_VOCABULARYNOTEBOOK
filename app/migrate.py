# app/migrate.py — apply migrations/*.sql in name order, each one only once.
#
# Run it against whatever DATABASE_URL points at:
#   python -m app.migrate
# Applied files are recorded in the schema_migrations table, so running it
# again is safe and only applies the new files.
#
# It then makes sure the admin account from ADMIN_EMAIL / ADMIN_PASSWORD exists
# (Render's free plan has no shell, so this is how the first admin is created).
import os
from pathlib import Path

from app.db import connect
from app.repository import UserRepository
from app.security import hash_password

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


def ensure_admin() -> str | None:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return None
    if len(password) < 8:
        raise SystemExit("ADMIN_PASSWORD must be at least 8 characters")
    with connect() as conn:
        UserRepository(conn).ensure_admin(email, "Admin", hash_password(password))
    return email


if __name__ == "__main__":
    names = migrate()
    print("applied:", ", ".join(names) if names else "nothing, schema is up to date")
    admin = ensure_admin()
    # The email is not a secret, but it is not printed either: logs are shared more widely.
    print("admin account:", "ready" if admin else "skipped (ADMIN_EMAIL / ADMIN_PASSWORD not set)")

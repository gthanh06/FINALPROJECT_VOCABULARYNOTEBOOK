# app/repository.py — every SQL query of the app lives here.
#
# The routes only talk to WordRepository / UserRepository, so the unit tests can
# swap them for in-memory fakes and run in CI without any database.
# A WordRepository is bound to one user: every query is limited to that user's words.
from datetime import UTC, datetime, timedelta

import psycopg

UPDATABLE = ("word", "meaning_vi", "part_of_speech", "example", "usage_note", "topic_id")


class DuplicateWord(Exception):
    """The word is already in the notebook (unique index on lower(word))."""


class UnknownTopic(Exception):
    """topic_id does not match any row in topics (foreign key)."""


class DuplicateEmail(Exception):
    """An account with this email already exists (unique index on lower(email))."""


class WordRepository:
    def __init__(self, conn: psycopg.Connection, user_id: int):
        self.conn = conn
        self.user_id = user_id

    def list_words(self, q: str | None = None) -> list[dict]:
        if q:
            return self.conn.execute(
                "SELECT * FROM words WHERE user_id = %s AND (word ILIKE %s OR meaning_vi ILIKE %s)"
                " ORDER BY created_at DESC, id DESC",
                (self.user_id, f"%{q}%", f"%{q}%"),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM words WHERE user_id = %s ORDER BY created_at DESC, id DESC",
            (self.user_id,),
        ).fetchall()

    def get_word(self, word_id: int) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM words WHERE id = %s AND user_id = %s", (word_id, self.user_id)
        ).fetchone()

    def create_word(self, data: dict) -> dict:
        try:
            return self.conn.execute(
                "INSERT INTO words"
                " (user_id, word, meaning_vi, part_of_speech, example, usage_note, topic_id)"
                " VALUES (%(user_id)s, %(word)s, %(meaning_vi)s, %(part_of_speech)s, %(example)s,"
                " %(usage_note)s, %(topic_id)s) RETURNING *",
                {**data, "user_id": self.user_id},
            ).fetchone()
        except psycopg.errors.UniqueViolation as err:
            raise DuplicateWord from err
        except psycopg.errors.ForeignKeyViolation as err:
            raise UnknownTopic from err

    def update_word(self, word_id: int, fields: dict) -> dict | None:
        fields = {k: v for k, v in fields.items() if k in UPDATABLE}
        if not fields:
            return self.get_word(word_id)
        # Column names come from the UPDATABLE whitelist, values are parameters.
        sets = ", ".join(f"{k} = %({k})s" for k in fields)
        try:
            return self.conn.execute(
                f"UPDATE words SET {sets} WHERE id = %(id)s AND user_id = %(user_id)s RETURNING *",
                {**fields, "id": word_id, "user_id": self.user_id},
            ).fetchone()
        except psycopg.errors.UniqueViolation as err:
            raise DuplicateWord from err
        except psycopg.errors.ForeignKeyViolation as err:
            raise UnknownTopic from err

    def list_topics(self) -> list[dict]:
        # Every topic, with how many of this user's words are in it (0 included).
        return self.conn.execute(
            "SELECT t.id, t.slug, t.name, t.icon, count(w.id) AS word_count"
            " FROM topics t LEFT JOIN words w ON w.topic_id = t.id AND w.user_id = %s"
            " GROUP BY t.id ORDER BY t.position",
            (self.user_id,),
        ).fetchall()

    def delete_word(self, word_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM words WHERE id = %s AND user_id = %s", (word_id, self.user_id)
        )
        return cur.rowcount == 1

    def add_review(self, word_id: int, result: str) -> dict | None:
        if self.get_word(word_id) is None:
            return None
        return self.conn.execute(
            "INSERT INTO review_logs (word_id, result) VALUES (%s, %s) RETURNING *",
            (word_id, result),
        ).fetchone()

    def list_reviews(self, word_id: int) -> list[dict] | None:
        if self.get_word(word_id) is None:
            return None
        return self.conn.execute(
            "SELECT * FROM review_logs WHERE word_id = %s ORDER BY reviewed_at DESC, id DESC",
            (word_id,),
        ).fetchall()


class UserRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create_user(self, email: str, display_name: str, password_hash: str) -> dict:
        try:
            return self.conn.execute(
                "INSERT INTO users (email, display_name, password_hash) VALUES (%s, %s, %s)"
                " RETURNING *",
                (email, display_name, password_hash),
            ).fetchone()
        except psycopg.errors.UniqueViolation as err:
            raise DuplicateEmail from err

    def get_user_by_email(self, email: str) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(%s)", (email,)
        ).fetchone()

    def copy_starter_words(self, user_id: int) -> int:
        # The seeded words (user_id NULL) become the new user's first notebook.
        cur = self.conn.execute(
            "INSERT INTO words"
            " (user_id, word, meaning_vi, part_of_speech, example, usage_note, topic_id)"
            " SELECT %s, word, meaning_vi, part_of_speech, example, usage_note, topic_id"
            " FROM words WHERE user_id IS NULL ORDER BY id",
            (user_id,),
        )
        return cur.rowcount

    def create_session(self, token_hash: str, user_id: int, days: int) -> None:
        # Expired sessions are cleaned up here instead of by a separate job.
        self.conn.execute("DELETE FROM sessions WHERE expires_at < now()")
        self.conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
            (token_hash, user_id, datetime.now(UTC) + timedelta(days=days)),
        )

    def get_session_user(self, token_hash: str) -> dict | None:
        return self.conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = %s AND s.expires_at > now()",
            (token_hash,),
        ).fetchone()

    def delete_session(self, token_hash: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))

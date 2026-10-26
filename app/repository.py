# app/repository.py — every SQL query of the app lives here.
#
# The routes only talk to WordRepository / UserRepository, so the unit tests can
# swap them for in-memory fakes and run in CI without any database.
# Words are shared by everyone; review history is kept per user.
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
    # Words are one shared bank (only admins change it, checked in the routes);
    # practice history is per user, so the repository is bound to one user.
    def __init__(self, conn: psycopg.Connection, user_id: int):
        self.conn = conn
        self.user_id = user_id

    def list_words(self, q: str | None = None) -> list[dict]:
        if q:
            return self.conn.execute(
                "SELECT * FROM words WHERE word ILIKE %s OR meaning_vi ILIKE %s"
                " ORDER BY created_at DESC, id DESC",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        return self.conn.execute("SELECT * FROM words ORDER BY created_at DESC, id DESC").fetchall()

    def get_word(self, word_id: int) -> dict | None:
        return self.conn.execute("SELECT * FROM words WHERE id = %s", (word_id,)).fetchone()

    def create_word(self, data: dict) -> dict:
        try:
            return self.conn.execute(
                "INSERT INTO words"
                " (word, meaning_vi, part_of_speech, example, usage_note, topic_id)"
                " VALUES (%(word)s, %(meaning_vi)s, %(part_of_speech)s, %(example)s,"
                " %(usage_note)s, %(topic_id)s) RETURNING *",
                data,
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
                f"UPDATE words SET {sets} WHERE id = %(id)s RETURNING *",
                {**fields, "id": word_id},
            ).fetchone()
        except psycopg.errors.UniqueViolation as err:
            raise DuplicateWord from err
        except psycopg.errors.ForeignKeyViolation as err:
            raise UnknownTopic from err

    def list_topics(self) -> list[dict]:
        # Every topic with its number of words (0 included).
        return self.conn.execute(
            "SELECT t.id, t.slug, t.name, t.icon, count(w.id) AS word_count"
            " FROM topics t LEFT JOIN words w ON w.topic_id = t.id"
            " GROUP BY t.id ORDER BY t.position"
        ).fetchall()

    def existing_words(self, words: list[str]) -> set[str]:
        # Which of these words (lower-cased) are already in the bank.
        rows = self.conn.execute(
            "SELECT lower(word) AS w FROM words WHERE lower(word) = ANY(%s)",
            ([w.lower() for w in words],),
        ).fetchall()
        return {r["w"] for r in rows}

    def import_words(self, rows: list[dict], update_existing: bool) -> None:
        # One request = one transaction (app/auth.py get_conn): all rows or none.
        on_conflict = (
            "DO UPDATE SET meaning_vi = EXCLUDED.meaning_vi,"
            " part_of_speech = EXCLUDED.part_of_speech, example = EXCLUDED.example,"
            " usage_note = EXCLUDED.usage_note, topic_id = EXCLUDED.topic_id"
            if update_existing
            else "DO NOTHING"
        )
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO words"
                " (word, meaning_vi, part_of_speech, example, usage_note, topic_id)"
                " VALUES (%(word)s, %(meaning_vi)s, %(part_of_speech)s, %(example)s,"
                f" %(usage_note)s, %(topic_id)s) ON CONFLICT ((lower(word))) {on_conflict}",
                rows,
            )

    def delete_word(self, word_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM words WHERE id = %s", (word_id,))
        return cur.rowcount == 1

    def add_review(self, word_id: int, result: str) -> dict | None:
        if self.get_word(word_id) is None:
            return None
        return self.conn.execute(
            "INSERT INTO review_logs (user_id, word_id, result) VALUES (%s, %s, %s) RETURNING *",
            (self.user_id, word_id, result),
        ).fetchone()

    def progress(self) -> dict:
        return progress(self.conn, self.user_id)

    def list_reviews(self, word_id: int) -> list[dict] | None:
        # Only this user's own practice history.
        if self.get_word(word_id) is None:
            return None
        return self.conn.execute(
            "SELECT * FROM review_logs WHERE word_id = %s AND user_id = %s"
            " ORDER BY reviewed_at DESC, id DESC",
            (word_id, self.user_id),
        ).fetchall()


# A word counts as "mastered" when this user's latest answer for it was right.
LATEST_ANSWERS = (
    "SELECT DISTINCT ON (word_id) word_id, result FROM review_logs"
    " WHERE user_id = %(user_id)s ORDER BY word_id, reviewed_at DESC, id DESC"
)
# Days are counted in Vietnam time, so "today" matches the learner's day.
LOCAL_DAY = "(reviewed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"


def progress(conn: psycopg.Connection, user_id: int) -> dict:
    p = {"user_id": user_id}
    totals = conn.execute(
        "SELECT count(*) AS answered,"
        " count(*) FILTER (WHERE result = 'remembered') AS correct,"
        " count(DISTINCT word_id) AS practiced"
        " FROM review_logs WHERE user_id = %(user_id)s",
        p,
    ).fetchone()
    topics = conn.execute(
        f"WITH latest AS ({LATEST_ANSWERS})"
        " SELECT t.id, t.slug, t.name, t.icon, count(w.id) AS total,"
        " count(l.word_id) AS practiced,"
        " count(l.word_id) FILTER (WHERE l.result = 'remembered') AS mastered"
        " FROM topics t LEFT JOIN words w ON w.topic_id = t.id"
        " LEFT JOIN latest l ON l.word_id = w.id"
        " GROUP BY t.id ORDER BY t.position",
        p,
    ).fetchall()
    mastered = conn.execute(
        f"SELECT count(*) AS n FROM ({LATEST_ANSWERS}) l WHERE l.result = 'remembered'", p
    ).fetchone()["n"]
    days = conn.execute(
        "SELECT d::date AS day, count(r.id) AS answered,"
        " count(r.id) FILTER (WHERE r.result = 'remembered') AS correct"
        " FROM generate_series((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 6,"
        " (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, interval '1 day') AS d"
        f" LEFT JOIN review_logs r ON r.user_id = %(user_id)s AND {LOCAL_DAY} = d::date"
        " GROUP BY d ORDER BY d",
        p,
    ).fetchall()
    to_review = conn.execute(
        f"WITH latest AS ({LATEST_ANSWERS})"
        " SELECT w.id, w.word, w.meaning_vi,"
        " (SELECT count(*) FROM review_logs r WHERE r.user_id = %(user_id)s"
        "  AND r.word_id = w.id AND r.result = 'forgot') AS forgot"
        " FROM latest l JOIN words w ON w.id = l.word_id"
        " WHERE l.result = 'forgot' ORDER BY forgot DESC, w.word LIMIT 10",
        p,
    ).fetchall()
    total_words = conn.execute("SELECT count(*) AS n FROM words").fetchone()["n"]
    return {
        **totals,
        "mastered": mastered,
        "total_words": total_words,
        "topics": topics,
        "last_7_days": days,
        "to_review": to_review,
    }


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

    def ensure_admin(self, email: str, display_name: str, password_hash: str) -> dict:
        # Creates the admin account, or turns an existing account with this email into
        # an admin. The password is reset too, so ADMIN_PASSWORD is always the one that works.
        user = self.get_user_by_email(email)
        if user is None:
            return self.conn.execute(
                "INSERT INTO users (email, display_name, password_hash, role)"
                " VALUES (%s, %s, %s, 'admin') RETURNING *",
                (email, display_name, password_hash),
            ).fetchone()
        return self.conn.execute(
            "UPDATE users SET role = 'admin', password_hash = %s WHERE id = %s RETURNING *",
            (password_hash, user["id"]),
        ).fetchone()

    def list_users(self) -> list[dict]:
        # For the admin page: every account with how much it has practiced.
        return self.conn.execute(
            "SELECT u.id, u.email, u.display_name, u.role, u.created_at,"
            " count(r.id) AS review_count,"
            " count(r.id) FILTER (WHERE r.result = 'remembered') AS remembered_count,"
            " max(r.reviewed_at) AS last_review_at"
            " FROM users u LEFT JOIN review_logs r ON r.user_id = u.id"
            " GROUP BY u.id ORDER BY u.created_at DESC"
        ).fetchall()

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

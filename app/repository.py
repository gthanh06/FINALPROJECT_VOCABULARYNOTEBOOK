# app/repository.py — every SQL query of the app lives here.
#
# The routes only talk to WordRepository, so the unit tests can swap it for an
# in-memory fake and run in CI without any database.
import psycopg

UPDATABLE = ("word", "meaning_vi", "part_of_speech", "example", "usage_note")


class DuplicateWord(Exception):
    """The word is already in the notebook (unique index on lower(word))."""


class WordRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

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
                "INSERT INTO words (word, meaning_vi, part_of_speech, example, usage_note)"
                " VALUES (%(word)s, %(meaning_vi)s, %(part_of_speech)s, %(example)s,"
                " %(usage_note)s) RETURNING *",
                data,
            ).fetchone()
        except psycopg.errors.UniqueViolation as err:
            raise DuplicateWord from err

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

    def delete_word(self, word_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM words WHERE id = %s", (word_id,))
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

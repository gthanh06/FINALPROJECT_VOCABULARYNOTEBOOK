# tests/fake_repo.py — same methods as app.repository's classes, kept in memory.
from datetime import UTC, datetime, timedelta

from app.repository import UPDATABLE, DuplicateEmail, DuplicateWord


class FakeStore:
    """Every user's words and reviews, like the words / review_logs tables."""

    def __init__(self):
        self.words: dict[int, dict] = {}
        self.reviews: list[dict] = []
        self.next_id = 1
        self.starter: list[dict] = []  # like the seeded words with user_id NULL

    def insert_word(self, user_id, data):
        row = {**data, "id": self.next_id, "user_id": user_id, "created_at": datetime.now(UTC)}
        self.words[row["id"]] = row
        self.next_id += 1
        return row


class FakeWordRepository:
    def __init__(self, store: FakeStore, user_id: int):
        self.store = store
        self.user_id = user_id

    def _mine(self):
        return [w for w in self.store.words.values() if w["user_id"] == self.user_id]

    def _taken(self, word: str, except_id: int | None = None) -> bool:
        return any(w["word"].lower() == word.lower() and w["id"] != except_id for w in self._mine())

    def list_words(self, q=None):
        rows = sorted(self._mine(), key=lambda w: w["id"], reverse=True)
        if q:
            q = q.lower()
            rows = [w for w in rows if q in w["word"].lower() or q in w["meaning_vi"].lower()]
        return rows

    def get_word(self, word_id):
        row = self.store.words.get(word_id)
        return row if row and row["user_id"] == self.user_id else None

    def create_word(self, data):
        if self._taken(data["word"]):
            raise DuplicateWord
        return self.store.insert_word(self.user_id, data)

    def update_word(self, word_id, fields):
        row = self.get_word(word_id)
        if row is None:
            return None
        if "word" in fields and self._taken(fields["word"], except_id=word_id):
            raise DuplicateWord
        row.update({k: v for k, v in fields.items() if k in UPDATABLE})
        return row

    def delete_word(self, word_id):
        if self.get_word(word_id) is None:
            return False
        del self.store.words[word_id]
        # ON DELETE CASCADE
        self.store.reviews = [r for r in self.store.reviews if r["word_id"] != word_id]
        return True

    def add_review(self, word_id, result):
        if self.get_word(word_id) is None:
            return None
        row = {
            "id": len(self.store.reviews) + 1,
            "word_id": word_id,
            "result": result,
            "reviewed_at": datetime.now(UTC),
        }
        self.store.reviews.append(row)
        return row

    def list_reviews(self, word_id):
        if self.get_word(word_id) is None:
            return None
        return [r for r in reversed(self.store.reviews) if r["word_id"] == word_id]


class FakeUserRepository:
    def __init__(self, store: FakeStore):
        self.store = store
        self.users: dict[int, dict] = {}
        self.sessions: dict[str, dict] = {}

    def create_user(self, email, display_name, password_hash):
        if self.get_user_by_email(email):
            raise DuplicateEmail
        row = {
            "id": len(self.users) + 1,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
            "created_at": datetime.now(UTC),
        }
        self.users[row["id"]] = row
        return row

    def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u["email"].lower() == email.lower()), None)

    def copy_starter_words(self, user_id):
        for w in self.store.starter:
            self.store.insert_word(user_id, w)
        return len(self.store.starter)

    def create_session(self, token_hash, user_id, days):
        expires = datetime.now(UTC) + timedelta(days=days)
        self.sessions[token_hash] = {"user_id": user_id, "expires_at": expires}

    def get_session_user(self, token_hash):
        s = self.sessions.get(token_hash)
        if s is None or s["expires_at"] <= datetime.now(UTC):
            return None
        return self.users[s["user_id"]]

    def delete_session(self, token_hash):
        self.sessions.pop(token_hash, None)

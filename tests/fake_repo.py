# tests/fake_repo.py — same methods as app.repository.WordRepository, kept in memory.
from datetime import UTC, datetime

from app.repository import UPDATABLE, DuplicateWord


class FakeWordRepository:
    def __init__(self):
        self.words: dict[int, dict] = {}
        self.reviews: list[dict] = []
        self.next_id = 1

    def _taken(self, word: str, except_id: int | None = None) -> bool:
        return any(
            w["word"].lower() == word.lower() and w["id"] != except_id for w in self.words.values()
        )

    def list_words(self, q=None):
        rows = sorted(self.words.values(), key=lambda w: w["id"], reverse=True)
        if q:
            q = q.lower()
            rows = [w for w in rows if q in w["word"].lower() or q in w["meaning_vi"].lower()]
        return rows

    def get_word(self, word_id):
        return self.words.get(word_id)

    def create_word(self, data):
        if self._taken(data["word"]):
            raise DuplicateWord
        row = {**data, "id": self.next_id, "created_at": datetime.now(UTC)}
        self.words[row["id"]] = row
        self.next_id += 1
        return row

    def update_word(self, word_id, fields):
        row = self.words.get(word_id)
        if row is None:
            return None
        if "word" in fields and self._taken(fields["word"], except_id=word_id):
            raise DuplicateWord
        row.update({k: v for k, v in fields.items() if k in UPDATABLE})
        return row

    def delete_word(self, word_id):
        if self.words.pop(word_id, None) is None:
            return False
        self.reviews = [r for r in self.reviews if r["word_id"] != word_id]  # ON DELETE CASCADE
        return True

    def add_review(self, word_id, result):
        if word_id not in self.words:
            return None
        row = {
            "id": len(self.reviews) + 1,
            "word_id": word_id,
            "result": result,
            "reviewed_at": datetime.now(UTC),
        }
        self.reviews.append(row)
        return row

    def list_reviews(self, word_id):
        if word_id not in self.words:
            return None
        return [r for r in reversed(self.reviews) if r["word_id"] == word_id]

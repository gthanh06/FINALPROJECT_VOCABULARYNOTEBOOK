# tests/fake_repo.py — same methods as app.repository's classes, kept in memory.
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.repository import UPDATABLE, DuplicateEmail, DuplicateWord, UnknownTopic


class FakeStore:
    """The shared words and everyone's reviews, like the words / review_logs tables."""

    def __init__(self):
        self.words: dict[int, dict] = {}
        self.reviews: list[dict] = []
        self.next_id = 1
        self.topics = [
            {"id": 1, "slug": "animals", "name": "Con vật", "icon": "🐾"},
            {"id": 2, "slug": "home", "name": "Nhà cửa & nội thất", "icon": "🛋️"},
        ]

    def check_topic(self, topic_id):
        if topic_id is not None and topic_id not in {t["id"] for t in self.topics}:
            raise UnknownTopic

    def insert_word(self, data):
        row = {**data, "id": self.next_id, "created_at": datetime.now(UTC)}
        self.words[row["id"]] = row
        self.next_id += 1
        return row


class FakeWordRepository:
    def __init__(self, store: FakeStore, user_id: int):
        self.store = store
        self.user_id = user_id

    def _taken(self, word: str, except_id: int | None = None) -> bool:
        return any(
            w["word"].lower() == word.lower() and w["id"] != except_id
            for w in self.store.words.values()
        )

    def list_words(self, q=None):
        rows = sorted(self.store.words.values(), key=lambda w: w["id"], reverse=True)
        if q:
            q = q.lower()
            rows = [w for w in rows if q in w["word"].lower() or q in w["meaning_vi"].lower()]
        return rows

    def get_word(self, word_id):
        return self.store.words.get(word_id)

    def create_word(self, data):
        if self._taken(data["word"]):
            raise DuplicateWord
        self.store.check_topic(data.get("topic_id"))
        return self.store.insert_word(data)

    def update_word(self, word_id, fields):
        row = self.get_word(word_id)
        if row is None:
            return None
        if "word" in fields and self._taken(fields["word"], except_id=word_id):
            raise DuplicateWord
        if "topic_id" in fields:
            self.store.check_topic(fields["topic_id"])
        row.update({k: v for k, v in fields.items() if k in UPDATABLE})
        return row

    def list_topics(self):
        words = self.store.words.values()
        return [
            {**t, "word_count": sum(w.get("topic_id") == t["id"] for w in words)}
            for t in self.store.topics
        ]

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
            "user_id": self.user_id,
            "word_id": word_id,
            "result": result,
            "reviewed_at": datetime.now(UTC),
        }
        self.store.reviews.append(row)
        return row

    def progress(self):
        mine = [r for r in self.store.reviews if r["user_id"] == self.user_id]
        latest = {}
        for r in mine:  # in insertion order, so the last one wins
            latest[r["word_id"]] = r["result"]
        words = self.store.words.values()
        topics = []
        for t in self.store.topics:
            ids = [w["id"] for w in words if w.get("topic_id") == t["id"]]
            topics.append({
                **t,
                "total": len(ids),
                "practiced": sum(i in latest for i in ids),
                "mastered": sum(latest.get(i) == "remembered" for i in ids),
            })
        vn = ZoneInfo("Asia/Ho_Chi_Minh")
        today = datetime.now(vn).date()
        days = []
        for k in range(6, -1, -1):
            day = today - timedelta(days=k)
            that_day = [r for r in mine if r["reviewed_at"].astimezone(vn).date() == day]
            days.append({
                "day": day,
                "answered": len(that_day),
                "correct": sum(r["result"] == "remembered" for r in that_day),
            })
        forgot = {
            i: sum(r["word_id"] == i and r["result"] == "forgot" for r in mine) for i in latest
        }
        to_review = sorted(
            (i for i, res in latest.items() if res == "forgot"),
            key=lambda i: (-forgot[i], self.store.words[i]["word"]),
        )[:10]
        return {
            "answered": len(mine),
            "correct": sum(r["result"] == "remembered" for r in mine),
            "practiced": len(latest),
            "mastered": sum(res == "remembered" for res in latest.values()),
            "total_words": len(self.store.words),
            "topics": topics,
            "last_7_days": days,
            "to_review": [{**self.store.words[i], "forgot": forgot[i]} for i in to_review],
        }

    def list_reviews(self, word_id):
        if self.get_word(word_id) is None:
            return None
        return [
            r for r in reversed(self.store.reviews)
            if r["word_id"] == word_id and r["user_id"] == self.user_id
        ]


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
            "role": "learner",
            "created_at": datetime.now(UTC),
        }
        self.users[row["id"]] = row
        return row

    def ensure_admin(self, email, display_name, password_hash):
        user = self.get_user_by_email(email) or self.create_user(email, display_name, password_hash)
        user.update(role="admin", password_hash=password_hash)
        return user

    def list_users(self):
        rows = []
        for u in sorted(self.users.values(), key=lambda u: u["id"], reverse=True):
            mine = [r for r in self.store.reviews if r["user_id"] == u["id"]]
            rows.append({
                **u,
                "review_count": len(mine),
                "remembered_count": sum(r["result"] == "remembered" for r in mine),
                "last_review_at": max((r["reviewed_at"] for r in mine), default=None),
            })
        return rows

    def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u["email"].lower() == email.lower()), None)

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

# app/schemas.py — the shapes of the JSON going in and out of the API.
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class WordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    meaning_vi: str = Field(min_length=1)
    part_of_speech: str | None = None
    # Left empty when the AI is busy; the user can fill them in later.
    example: str | None = None
    usage_note: str | None = None
    topic_id: int | None = None  # None = "Uncategorized"


class WordUpdate(BaseModel):
    # Every field is optional: only the fields sent are changed.
    word: str | None = Field(default=None, min_length=1, max_length=100)
    meaning_vi: str | None = Field(default=None, min_length=1)
    part_of_speech: str | None = None
    example: str | None = None
    usage_note: str | None = None
    topic_id: int | None = None


class Word(WordCreate):
    id: int
    created_at: datetime


class Topic(BaseModel):
    id: int
    slug: str
    name: str
    icon: str
    word_count: int  # how many words the logged-in user has in this topic


ReviewResult = Literal["remembered", "forgot"]


class ReviewCreate(BaseModel):
    result: ReviewResult


Direction = Literal["en-vi", "vi-en"]


class AnswerIn(BaseModel):
    direction: Direction
    answer: str = Field(max_length=200)


class AnswerResult(BaseModel):
    verdict: Literal["correct", "accent", "close", "wrong"]
    correct: bool
    expected: str


class Review(BaseModel):
    id: int
    word_id: int
    reviewed_at: datetime
    result: ReviewResult


class ImportIn(BaseModel):
    csv: str = Field(max_length=3_000_000)  # about 3 MB of text
    # False: words already in the bank are skipped. True: they are overwritten.
    update_existing: bool = False
    # True: only check the file and report, save nothing.
    dry_run: bool = True


class ImportLineError(BaseModel):
    line: int
    message: str


class ImportPreviewRow(BaseModel):
    word: str
    meaning_vi: str
    part_of_speech: str | None
    topic_id: int | None
    exists: bool


class ImportResult(BaseModel):
    saved: bool
    total: int  # valid rows in the file
    new: int
    existing: int  # updated if update_existing, otherwise skipped
    errors: list[ImportLineError]
    sample: list[ImportPreviewRow]  # the first rows, to eyeball before saving


# A light email check; the real proof would be a confirmation email.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    # True from the "Admin" sign-in form: only admin accounts may log in there.
    admin: bool = False


Role = Literal["learner", "admin"]


class User(BaseModel):
    # Never includes password_hash.
    id: int
    email: str
    display_name: str
    role: Role
    created_at: datetime


class TopicProgress(BaseModel):
    id: int
    slug: str
    name: str
    icon: str
    total: int  # words in the topic
    practiced: int  # of those, words this user has answered at least once
    mastered: int  # of those, words whose latest answer was right


class DayActivity(BaseModel):
    day: date
    answered: int
    correct: int


class WordToReview(BaseModel):
    id: int
    word: str
    meaning_vi: str
    forgot: int


class Progress(BaseModel):
    answered: int
    correct: int
    practiced: int
    mastered: int
    total_words: int
    topics: list[TopicProgress]
    last_7_days: list[DayActivity]
    to_review: list[WordToReview]


class UserSummary(User):
    # One row of the admin page's learner table.
    review_count: int
    remembered_count: int
    last_review_at: datetime | None

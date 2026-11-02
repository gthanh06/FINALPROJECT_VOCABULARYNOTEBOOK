# app/schemas.py — the shapes of the JSON going in and out of the API.
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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


# ---------- My notebook (user_words): every user's own words ----------
WordSource = Literal["manual", "bank", "ai"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Example(BaseModel):
    en: str = Field(min_length=1, max_length=300)
    vi: str | None = Field(default=None, max_length=300)


class NotebookWordCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    word: str = Field(min_length=1, max_length=100)
    meaning_vi: str = Field(min_length=1, max_length=300)
    ipa: str | None = Field(default=None, max_length=100)
    part_of_speech: str | None = Field(default=None, max_length=30)
    definition_en: str | None = Field(default=None, max_length=500)
    examples: list[Example] = Field(default_factory=list, max_length=5)
    synonyms: list[ShortText] = Field(default_factory=list, max_length=20)
    antonyms: list[ShortText] = Field(default_factory=list, max_length=20)
    collocations: list[ShortText] = Field(default_factory=list, max_length=20)
    usage_note: str | None = Field(default=None, max_length=1000)
    topic_id: int | None = None
    source: Literal["manual", "ai"] = "manual"


class NotebookWordUpdate(BaseModel):
    # Every field is optional: only the fields sent are changed.
    model_config = ConfigDict(str_strip_whitespace=True)

    word: str | None = Field(default=None, min_length=1, max_length=100)
    meaning_vi: str | None = Field(default=None, min_length=1, max_length=300)
    ipa: str | None = Field(default=None, max_length=100)
    part_of_speech: str | None = Field(default=None, max_length=30)
    definition_en: str | None = Field(default=None, max_length=500)
    examples: list[Example] | None = Field(default=None, max_length=5)
    synonyms: list[ShortText] | None = Field(default=None, max_length=20)
    antonyms: list[ShortText] | None = Field(default=None, max_length=20)
    collocations: list[ShortText] | None = Field(default=None, max_length=20)
    usage_note: str | None = Field(default=None, max_length=1000)
    topic_id: int | None = None


class NotebookWord(BaseModel):
    id: int
    word: str
    meaning_vi: str
    ipa: str | None
    part_of_speech: str | None
    definition_en: str | None
    examples: list[Example]
    synonyms: list[str]
    antonyms: list[str]
    collocations: list[str]
    usage_note: str | None
    topic_id: int | None
    source: WordSource
    bank_word_id: int | None
    created_at: datetime
    updated_at: datetime


class QuizStartIn(BaseModel):
    count: int = Field(default=10, ge=3, le=30)


class QuizQuestion(BaseModel):
    id: int
    kind: Literal["multiple_choice", "fill_blank", "meaning"]
    prompt: str
    choices: list[str] | None = None


class QuizStartOut(BaseModel):
    quiz_id: int
    questions: list[QuizQuestion]


class QuizAnswerIn(BaseModel):
    question_id: int
    answer: str = Field(max_length=300)


class QuizSubmitIn(BaseModel):
    answers: list[QuizAnswerIn] = Field(min_length=1, max_length=30)


class QuizQuestionResult(QuizQuestion):
    answer: str
    expected: str
    correct: bool


class QuizResult(BaseModel):
    score: int
    total: int
    questions: list[QuizQuestionResult]


class SrsReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5)


class SrsWord(BaseModel):
    id: int
    word: str
    meaning_vi: str
    part_of_speech: str | None
    definition_en: str | None
    examples: list[Example]
    srs_level: int
    srs_ease: float
    srs_interval: int
    next_review: date | None


class SrsToday(BaseModel):
    due: int
    cards: list[SrsWord]


class SrsReviewResult(BaseModel):
    level: int
    ease: float
    interval_days: int
    next_review: date


class Mnemonic(BaseModel):
    mnemonic: str = Field(min_length=1, max_length=500)


class MnemonicOut(Mnemonic):
    cached: bool

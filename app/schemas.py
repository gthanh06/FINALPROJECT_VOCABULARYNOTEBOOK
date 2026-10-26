# app/schemas.py — the shapes of the JSON going in and out of the API.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    meaning_vi: str = Field(min_length=1)
    part_of_speech: str | None = None
    # Left empty when the AI is busy; the user can fill them in later.
    example: str | None = None
    usage_note: str | None = None


class WordUpdate(BaseModel):
    # Every field is optional: only the fields sent are changed.
    word: str | None = Field(default=None, min_length=1, max_length=100)
    meaning_vi: str | None = Field(default=None, min_length=1)
    part_of_speech: str | None = None
    example: str | None = None
    usage_note: str | None = None


class Word(WordCreate):
    id: int
    created_at: datetime


ReviewResult = Literal["remembered", "forgot"]


class ReviewCreate(BaseModel):
    result: ReviewResult


class Review(BaseModel):
    id: int
    word_id: int
    reviewed_at: datetime
    result: ReviewResult


# A light email check; the real proof would be a confirmation email.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class User(BaseModel):
    # Never includes password_hash.
    id: int
    email: str
    display_name: str
    created_at: datetime

# app/routes.py — CRUD API for words and their review logs.
# Every route needs a logged-in user and only sees that user's notebook.
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import CurrentUser, get_conn
from app.grading import check
from app.repository import DuplicateWord, UnknownTopic, WordRepository
from app.schemas import (
    AnswerIn,
    AnswerResult,
    Review,
    ReviewCreate,
    Topic,
    Word,
    WordCreate,
    WordUpdate,
)

router = APIRouter(prefix="/api")


def get_repo(
    conn: Annotated[psycopg.Connection, Depends(get_conn)], user: CurrentUser
) -> WordRepository:
    return WordRepository(conn, user["id"])


Repo = Annotated[WordRepository, Depends(get_repo)]


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Không tìm thấy từ này")


def unknown_topic() -> HTTPException:
    return HTTPException(status_code=422, detail="Chủ đề không tồn tại")


@router.get("/topics", response_model=list[Topic])
def list_topics(repo: Repo):
    return repo.list_topics()


@router.get("/words", response_model=list[Word])
def list_words(repo: Repo, q: str | None = None):
    return repo.list_words(q)


@router.post("/words", response_model=Word, status_code=201)
def create_word(body: WordCreate, repo: Repo):
    try:
        return repo.create_word(body.model_dump())
    except DuplicateWord:
        raise HTTPException(status_code=409, detail="Từ này đã có trong sổ") from None
    except UnknownTopic:
        raise unknown_topic() from None


@router.get("/words/{word_id}", response_model=Word)
def get_word(word_id: int, repo: Repo):
    word = repo.get_word(word_id)
    if word is None:
        raise not_found()
    return word


@router.patch("/words/{word_id}", response_model=Word)
def update_word(word_id: int, body: WordUpdate, repo: Repo):
    try:
        word = repo.update_word(word_id, body.model_dump(exclude_unset=True))
    except DuplicateWord:
        raise HTTPException(status_code=409, detail="Từ này đã có trong sổ") from None
    except UnknownTopic:
        raise unknown_topic() from None
    if word is None:
        raise not_found()
    return word


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, repo: Repo):
    if not repo.delete_word(word_id):
        raise not_found()
    return Response(status_code=204)


@router.post("/words/{word_id}/check", response_model=AnswerResult)
def check_answer(word_id: int, body: AnswerIn, repo: Repo):
    # Grades only; the page then logs the final result with POST .../reviews, so the
    # learner can still overrule a "wrong" (e.g. a synonym) before it is saved.
    word = repo.get_word(word_id)
    if word is None:
        raise not_found()
    return check(word, body.direction, body.answer)


@router.post("/words/{word_id}/reviews", response_model=Review, status_code=201)
def add_review(word_id: int, body: ReviewCreate, repo: Repo):
    review = repo.add_review(word_id, body.result)
    if review is None:
        raise not_found()
    return review


@router.get("/words/{word_id}/reviews", response_model=list[Review])
def list_reviews(word_id: int, repo: Repo):
    reviews = repo.list_reviews(word_id)
    if reviews is None:
        raise not_found()
    return reviews

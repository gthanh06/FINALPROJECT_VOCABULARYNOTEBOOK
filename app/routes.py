# app/routes.py — CRUD API for words and their review logs.
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import connect
from app.repository import DuplicateWord, WordRepository
from app.schemas import Review, ReviewCreate, Word, WordCreate, WordUpdate

router = APIRouter(prefix="/api")


def get_repo() -> Iterator[WordRepository]:
    # One connection per request; leaving the "with" commits, an exception rolls back.
    with connect() as conn:
        yield WordRepository(conn)


Repo = Annotated[WordRepository, Depends(get_repo)]


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Không tìm thấy từ này")


@router.get("/words", response_model=list[Word])
def list_words(repo: Repo, q: str | None = None):
    return repo.list_words(q)


@router.post("/words", response_model=Word, status_code=201)
def create_word(body: WordCreate, repo: Repo):
    try:
        return repo.create_word(body.model_dump())
    except DuplicateWord:
        raise HTTPException(status_code=409, detail="Từ này đã có trong sổ") from None


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
    if word is None:
        raise not_found()
    return word


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, repo: Repo):
    if not repo.delete_word(word_id):
        raise not_found()
    return Response(status_code=204)


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

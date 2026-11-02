# app/notebook.py — "My notebook": every user's own words (user_words).
#
# GET    /api/notebook/words              my words (?q= searches word and meaning)
# POST   /api/notebook/words              add a word
# GET    /api/notebook/words/{id}         one of my words
# PATCH  /api/notebook/words/{id}         change the fields sent
# DELETE /api/notebook/words/{id}         remove it from my notebook
# POST   /api/notebook/from-bank/{id}     copy a word of the shared bank into my notebook
#
# Learners and admins both have a notebook. Nobody can see or change another user's words:
# the repository is bound to the logged-in user and every query filters on it.
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response

from app import ai
from app.auth import CurrentUser, get_conn
from app.repository import DuplicateWord, NotebookRepository, UnknownTopic
from app.schemas import (
    AiSuggestIn,
    AiSuggestion,
    NotebookWord,
    NotebookWordCreate,
    NotebookWordUpdate,
)

router = APIRouter(prefix="/api/notebook")

LIST_FIELDS = ("synonyms", "antonyms", "collocations")


def get_notebook(
    conn: Annotated[psycopg.Connection, Depends(get_conn)], user: CurrentUser
) -> NotebookRepository:
    return NotebookRepository(conn, user["id"])


Notebook = Annotated[NotebookRepository, Depends(get_notebook)]


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Không tìm thấy từ này trong sổ của bạn")


def duplicate_word() -> HTTPException:
    return HTTPException(status_code=409, detail="Từ này đã có trong sổ của bạn")


def unknown_topic() -> HTTPException:
    return HTTPException(status_code=422, detail="Chủ đề không tồn tại")


def clean(data: dict) -> dict:
    """Empty strings become NULL, list items are de-duplicated (case-insensitive)."""
    out = {}
    for k, v in data.items():
        if isinstance(v, str) and k not in ("word", "meaning_vi"):
            v = v or None
        if k in LIST_FIELDS and v is not None:
            seen, items = set(), []
            for item in v:
                if item.lower() not in seen:
                    seen.add(item.lower())
                    items.append(item)
            v = items
        if k == "examples" and v is not None:
            v = [{"en": e["en"].strip(), "vi": (e.get("vi") or "").strip() or None} for e in v]
        out[k] = v
    return out


@router.post("/ai-suggest", response_model=AiSuggestion)
def ai_suggest(body: AiSuggestIn, _: CurrentUser):
    try:
        return ai.suggest(body)
    except ai.AIServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None


@router.get("/words", response_model=list[NotebookWord])
def list_words(notebook: Notebook, q: str | None = None):
    return notebook.list_words(q)


@router.post("/words", response_model=NotebookWord, status_code=201)
def create_word(body: NotebookWordCreate, notebook: Notebook):
    try:
        return notebook.create_word(clean(body.model_dump()))
    except DuplicateWord:
        raise duplicate_word() from None
    except UnknownTopic:
        raise unknown_topic() from None


@router.get("/words/{word_id}", response_model=NotebookWord)
def get_word(word_id: int, notebook: Notebook):
    word = notebook.get_word(word_id)
    if word is None:
        raise not_found()
    return word


@router.patch("/words/{word_id}", response_model=NotebookWord)
def update_word(word_id: int, body: NotebookWordUpdate, notebook: Notebook):
    fields = clean(body.model_dump(exclude_unset=True))
    # word and meaning_vi are required: a null leaves them as they are; a null list empties it.
    for k in ("word", "meaning_vi"):
        if k in fields and fields[k] is None:
            del fields[k]
    for k in ("examples", *LIST_FIELDS):
        if k in fields and fields[k] is None:
            fields[k] = []
    try:
        word = notebook.update_word(word_id, fields)
    except DuplicateWord:
        raise duplicate_word() from None
    except UnknownTopic:
        raise unknown_topic() from None
    if word is None:
        raise not_found()
    return word


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, notebook: Notebook):
    if not notebook.delete_word(word_id):
        raise not_found()
    return Response(status_code=204)


@router.post("/from-bank/{bank_word_id}", response_model=NotebookWord, status_code=201)
def add_from_bank(bank_word_id: int, notebook: Notebook):
    bank = notebook.get_bank_word(bank_word_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Word not found")
    data = {
        "word": bank["word"],
        "meaning_vi": bank["meaning_vi"],
        "part_of_speech": bank.get("part_of_speech"),
        "examples": [{"en": bank["example"], "vi": None}] if bank.get("example") else [],
        "usage_note": bank.get("usage_note"),
        "topic_id": bank.get("topic_id"),
        "source": "bank",
        "bank_word_id": bank["id"],
    }
    try:
        return notebook.create_word(data)
    except DuplicateWord:
        raise duplicate_word() from None

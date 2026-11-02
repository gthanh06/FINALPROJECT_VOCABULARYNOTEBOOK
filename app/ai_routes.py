# app/ai_routes.py — AI features. The browser only talks to these routes; the Gemini key
# never leaves the server (app/ai/).
#
# GET  /api/ai/status   is AI on, which model, my limits and usage today
# POST /api/ai/lookup   {"word": "resilient"} -> meaning, IPA, examples... to review before saving
# POST /api/ai/check-sentence  {"word_id": 3, "sentence": "..."} -> verdict, errors explained
#                       in Vietnamese, corrected sentence (word_id is one of my notebook words)
#
# Every route needs a logged-in user. Calls that reach the AI count towards the
# user's limits (app/ratelimit.py); cached answers do not.
import hashlib
import re
from typing import Annotated, TypeVar

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app import ratelimit
from app.ai.errors import AIError, AINotConfigured
from app.ai.schemas import SentenceCheck, WordLookup
from app.ai.service import AIService, get_ai
from app.auth import CurrentUser, get_conn
from app.notebook import Notebook
from app.repository import AIRepository

router = APIRouter(prefix="/api/ai")

M = TypeVar("M", bound=BaseModel)

# Letters, spaces, apostrophes and hyphens only: "look after", "mother-in-law", "don't".
WORD_PATTERN = re.compile(r"^[a-z][a-z' -]{0,59}$")


def get_ai_repo(conn: Annotated[psycopg.Connection, Depends(get_conn)]) -> AIRepository:
    return AIRepository(conn)


AIRepo = Annotated[AIRepository, Depends(get_ai_repo)]
MaybeAI = Annotated[AIService | None, Depends(get_ai)]


def require_ai(ai: MaybeAI) -> AIService:
    if ai is None:
        raise ai_http_error(AINotConfigured())
    return ai


AI = Annotated[AIService, Depends(require_ai)]


def ai_http_error(err: AIError) -> HTTPException:
    headers = {"Retry-After": "60"} if err.status_code == 503 else None
    return HTTPException(status_code=err.status_code, detail=err.message, headers=headers)


class AIStatus(BaseModel):
    enabled: bool
    model: str | None
    limit_per_minute: int
    limit_per_day: int
    used_today: int


@router.get("/status", response_model=AIStatus)
def status(ai: MaybeAI, repo: AIRepo, user: CurrentUser):
    per_minute, per_day = ratelimit.limits()
    return {
        "enabled": ai is not None,
        "model": ai.model if ai else None,
        "limit_per_minute": per_minute,
        "limit_per_day": per_day,
        "used_today": ratelimit.used_today(repo, user["id"]),
    }


class LookupIn(BaseModel):
    word: str = Field(min_length=1, max_length=60)


class LookupOut(BaseModel):
    result: WordLookup
    cached: bool  # true: answered from the cache, no AI call was made
    topic_id: int | None  # the suggested topic, as an id of the topics table


def cached_answer(
    repo: AIRepository, kind: str, key: str, version: str, output: type[M]
) -> M | None:
    data = repo.cache_get(kind, key, version)
    if data is None:
        return None
    try:
        return output.model_validate(data)
    except ValidationError:
        # Saved by an older version of the schema: ask the AI again instead of failing.
        return None


def normalize_word(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


@router.post("/lookup", response_model=LookupOut)
def lookup(body: LookupIn, ai: AI, repo: AIRepo, user: CurrentUser):
    word = normalize_word(body.word)
    if not WORD_PATTERN.match(word):
        raise HTTPException(
            status_code=422,
            detail="Hãy nhập một từ hoặc cụm từ tiếng Anh (chỉ chữ cái, dấu cách, ' và -).",
        )
    topics = repo.topics()
    topic_ids = {t["slug"]: t["id"] for t in topics}
    version = ai.prompt_version("lookup")

    result = cached_answer(repo, "lookup", word, version, WordLookup)
    if result is not None:
        return {"result": result, "cached": True, "topic_id": topic_ids.get(result.topic)}

    try:
        with ratelimit.counted(repo, user["id"], "lookup"):
            result = ai.run("lookup", WordLookup, word=word, topics=", ".join(topic_ids))
    except AIError as err:
        raise ai_http_error(err) from None
    if result.topic not in topic_ids:
        result.topic = None
    # Only real words are kept: a "not a word" verdict may be a model mistake.
    if result.is_english_word:
        repo.cache_put("lookup", word, version, ai.model, result.model_dump())
    return {"result": result, "cached": False, "topic_id": topic_ids.get(result.topic)}


# ---------- Kiểm tra câu tự đặt ----------
class SentenceIn(BaseModel):
    word_id: int  # one of my notebook words
    sentence: str = Field(min_length=3, max_length=300)


class SentenceOut(BaseModel):
    result: SentenceCheck
    cached: bool


def is_form_of(form: str, word: str) -> bool:
    """Regular inflections only: readers, persevered, studies. Irregular ones (went) fail."""
    form, word = form.strip().lower(), word.strip().lower()
    stems = {word, word[:-1] if word.endswith(("e", "y")) else word}
    return bool(form) and any(form.startswith(stem) for stem in stems)


def keeps_word(result: SentenceCheck, word: str) -> bool:
    # The corrected (and better) sentence must still practise the target word.
    form = result.word_form.lower()
    sentences = [result.corrected, result.better_version or form]
    return is_form_of(form, word) and all(form in s.lower() for s in sentences)


def sentence_key(word: dict, sentence: str) -> str:
    # The verdict depends on the word, the meaning studied and the exact sentence.
    raw = "\n".join([word["word"].lower(), word.get("part_of_speech") or "", word["meaning_vi"],
                     sentence])
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/check-sentence", response_model=SentenceOut)
def check_sentence(
    body: SentenceIn, ai: AI, repo: AIRepo, notebook: Notebook, user: CurrentUser
):
    word = notebook.get_word(body.word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ này trong sổ của bạn")
    sentence = " ".join(body.sentence.split())
    if len(sentence) < 3:
        raise HTTPException(status_code=422, detail="Hãy viết một câu tiếng Anh.")
    key = sentence_key(word, sentence)
    version = ai.prompt_version("check_sentence")

    result = cached_answer(repo, "sentence", key, version, SentenceCheck)
    if result is not None:
        return {"result": result, "cached": True}

    try:
        with ratelimit.counted(repo, user["id"], "check_sentence"):
            result = ai.run(
                "check_sentence", SentenceCheck,
                accept=lambda r: keeps_word(r, word["word"]),
                word=word["word"], part_of_speech=word.get("part_of_speech") or "any",
                meaning_vi=word["meaning_vi"], sentence=sentence,
            )
    except AIError as err:
        raise ai_http_error(err) from None
    repo.cache_put("sentence", key, version, ai.model, result.model_dump())
    return {"result": result, "cached": False}

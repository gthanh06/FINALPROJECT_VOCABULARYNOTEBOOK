# app/ai_routes.py — AI features. The browser only talks to these routes; the Gemini key
# never leaves the server (app/ai/).
#
# GET  /api/ai/status   is AI on, which model, my limits and usage today
# POST /api/ai/lookup   {"word": "resilient"} -> meaning, IPA, examples... to review before saving
#
# Every route needs a logged-in user. Calls that reach the AI count towards the
# user's limits (app/ratelimit.py); cached answers do not.
import re
from typing import Annotated, TypeVar

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app import ratelimit
from app.ai.errors import AIError, AINotConfigured
from app.ai.schemas import WordLookup
from app.ai.service import AIService, get_ai
from app.auth import CurrentUser, get_conn
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

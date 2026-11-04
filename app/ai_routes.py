# app/ai_routes.py — AI features. The browser only talks to these routes; the Gemini key
# never leaves the server (app/ai/).
#
# GET  /api/ai/status   is AI on, which model, my limits and usage today
# POST /api/ai/lookup   {"word": "resilient"} -> meaning, IPA, examples... to review before saving
# POST /api/ai/check-sentence  {"word_id": 3, "sentence": "..."} -> verdict, errors explained
#                       in Vietnamese, corrected sentence (word_id is one of my notebook words)
# POST /api/ai/suggest-words  {"topic_id": 3, "level": "B1", "exclude": [...]} -> about 10 new
#                       words for that topic and level, minus the words already in my notebook
# POST /api/ai/chat     {"word_ids": [...], "messages": [...]} -> the tutor's next chat message,
#                       using my notebook words; the browser keeps the conversation
#
# Every route needs a logged-in user. Calls that reach the AI count towards the
# user's limits (app/ratelimit.py); cached answers do not.
import hashlib
import re
from typing import Annotated, Literal, TypeVar

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app import ratelimit
from app.ai.errors import AIError, AINotConfigured
from app.ai.schemas import (
    ChatReply,
    SentenceCheck,
    SuggestedWord,
    WordLookup,
    WordSuggestions,
)
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
            detail=(
                "Enter an English word or phrase (letters, spaces, apostrophes, and hyphens only)."
            ),
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


# ---------- Check a learner sentence ----------
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
        raise HTTPException(status_code=404, detail="This word was not found in your notebook.")
    sentence = " ".join(body.sentence.split())
    if len(sentence) < 3:
        raise HTTPException(status_code=422, detail="Write an English sentence.")
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


# ---------- Suggest words by topic + level ----------
SUGGEST_COUNT = 10


class SuggestIn(BaseModel):
    topic_id: int
    level: Literal["A1", "A2", "B1", "B2", "C1"]
    # Words already shown on the page ("Suggest more" must not repeat them).
    exclude: list[Annotated[str, Field(max_length=60)]] = Field(
        default_factory=list, max_length=100
    )


class SuggestOut(BaseModel):
    words: list[SuggestedWord]
    topic_id: int
    cached: bool


def new_words(words: list[SuggestedWord], avoid: set[str]) -> list[SuggestedWord]:
    """Drops words to avoid, duplicates and anything that is not a plain English word."""
    out, seen = [], set(avoid)
    for w in words:
        key = normalize_word(w.word)
        if key in seen or not WORD_PATTERN.match(key):
            continue
        seen.add(key)
        out.append(w.model_copy(update={"word": key}))
    return out


@router.post("/suggest-words", response_model=SuggestOut)
def suggest_words(body: SuggestIn, ai: AI, repo: AIRepo, notebook: Notebook, user: CurrentUser):
    topic = next((t for t in repo.topics() if t["id"] == body.topic_id), None)
    if topic is None:
        raise HTTPException(status_code=404, detail="This topic was not found.")
    mine = {normalize_word(w["word"]) for w in notebook.list_words()}
    shown = {normalize_word(w) for w in body.exclude}
    key = f"{topic['slug']}|{body.level}"
    version = ai.prompt_version("suggest_words")

    # The first list for a topic and level is shared by everyone; "more" is always fresh.
    if not shown:
        cached = cached_answer(repo, "suggest", key, version, WordSuggestions)
        if cached is not None:
            words = new_words(cached.words, mine)
            if len(words) >= 3:
                return {"words": words, "topic_id": topic["id"], "cached": True}

    avoid = sorted(mine | shown)
    try:
        with ratelimit.counted(repo, user["id"], "suggest_words"):
            result = ai.run(
                "suggest_words", WordSuggestions,
                topic=topic["name"], level=body.level, count=SUGGEST_COUNT,
                avoid=", ".join(avoid[-150:]) or "(none)",
            )
    except AIError as err:
        raise ai_http_error(err) from None
    if not shown:
        repo.cache_put("suggest", key, version, ai.model, result.model_dump())
    words = new_words(result.words, mine | shown)
    return {"words": words, "topic_id": topic["id"], "cached": False}


# ---------- Conversation practice (chatbot using notebook words) ----------
class ChatMessage(BaseModel):
    role: Literal["learner", "tutor"]
    text: str = Field(min_length=1, max_length=500)


class ChatIn(BaseModel):
    word_ids: list[int] = Field(min_length=1, max_length=10)  # words to practise, from my notebook
    messages: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatOut(BaseModel):
    reply: ChatReply


def transcript(messages: list[ChatMessage]) -> str:
    if not messages:
        return "(no messages yet: start the conversation)"
    names = {"learner": "Learner", "tutor": "Tutor"}
    return "\n".join(f"{names[m.role]}: {' '.join(m.text.split())}" for m in messages)


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, ai: AI, repo: AIRepo, notebook: Notebook, user: CurrentUser):
    if body.messages and body.messages[-1].role != "learner":
        raise HTTPException(status_code=422, detail="The last message must be yours.")
    mine = {w["id"]: w for w in notebook.list_words()}
    words = [mine[i] for i in dict.fromkeys(body.word_ids) if i in mine]
    if len(words) != len(set(body.word_ids)):
        raise HTTPException(status_code=404, detail="This word was not found in your notebook.")
    targets = "\n".join(f"- {w['word']}: {w['meaning_vi']}" for w in words)
    try:
        with ratelimit.counted(repo, user["id"], "chat"):
            reply = ai.run(
                "chat", ChatReply, words=targets, conversation=transcript(body.messages)
            )
    except AIError as err:
        raise ai_http_error(err) from None
    # Only the target words count as "used"; the first message has nothing to check.
    allowed = {normalize_word(w["word"]) for w in words}
    used = [w for w in map(normalize_word, reply.learner_used) if w in allowed]
    reply.learner_used = list(dict.fromkeys(used)) if body.messages else []
    if not body.messages:
        reply.correction = None
    return {"reply": reply}

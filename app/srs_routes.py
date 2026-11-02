"""Spaced repetition for words saved in the logged-in user's notebook."""
from fastapi import APIRouter, HTTPException

from app.ai.errors import AIError
from app.ai_routes import AI, AIRepo, ai_http_error, cached_answer, normalize_word
from app.auth import CurrentUser
from app.notebook import Notebook
from app.ratelimit import counted
from app.schemas import Mnemonic, MnemonicOut, SrsReviewIn, SrsReviewResult, SrsToday
from app.srs import vietnam_today

router = APIRouter(prefix="/api/srs")


@router.get("/today", response_model=SrsToday)
def today(notebook: Notebook):
    cards = notebook.list_due(vietnam_today())
    return {"due": len(cards), "cards": cards}


@router.post("/words/{word_id}/review", response_model=SrsReviewResult)
def review_word(word_id: int, body: SrsReviewIn, notebook: Notebook):
    result = notebook.review_srs(word_id, body.quality, vietnam_today())
    if result is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ này trong sổ của bạn")
    return result


@router.get("/words/{word_id}/reviews")
def review_history(word_id: int, notebook: Notebook):
    reviews = notebook.list_reviews_srs(word_id)
    if reviews is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ này trong sổ của bạn")
    return reviews


@router.post("/words/{word_id}/mnemonic", response_model=MnemonicOut)
def mnemonic(
    word_id: int,
    notebook: Notebook,
    ai: AI,
    repo: AIRepo,
    user: CurrentUser,
):
    word = notebook.get_word(word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ này trong sổ của bạn")
    key = f"{normalize_word(word['word'])}|{word['meaning_vi'].strip().casefold()}"
    version = ai.prompt_version("mnemonic")
    result = cached_answer(repo, "mnemonic", key, version, Mnemonic)
    if result is not None:
        return {**result.model_dump(), "cached": True}
    try:
        with counted(repo, user["id"], "mnemonic"):
            result = ai.run(
                "mnemonic", Mnemonic, word=word["word"], meaning_vi=word["meaning_vi"]
            )
    except AIError as err:
        raise ai_http_error(err) from None
    repo.cache_put("mnemonic", key, version, ai.model, result.model_dump())
    return {**result.model_dump(), "cached": False}

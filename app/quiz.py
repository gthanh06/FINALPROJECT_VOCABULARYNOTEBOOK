"""Server-graded quizzes built only from the logged-in user's notebook."""
import random
import re
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_conn
from app.notebook import Notebook
from app.repository import QuizRepository
from app.schemas import QuizResult, QuizStartIn, QuizStartOut, QuizSubmitIn

router = APIRouter(prefix="/api/quiz")


def get_quiz_repo(
    conn: Annotated[psycopg.Connection, Depends(get_conn)], user: CurrentUser
) -> QuizRepository:
    return QuizRepository(conn, user["id"])


QuizRepo = Annotated[QuizRepository, Depends(get_quiz_repo)]


def _choices(answer: str, candidates: list[str]) -> list[str]:
    others = list(
        dict.fromkeys(value for value in candidates if value.casefold() != answer.casefold())
    )
    random.shuffle(others)
    options = [answer, *others[:3]]
    random.shuffle(options)
    return options


def _fill_prompt(word: dict) -> str:
    examples = word.get("examples") or []
    for example in examples:
        sentence = example.get("en", "")
        pattern = rf"(?<![A-Za-z]){re.escape(word['word'])}(?![A-Za-z])"
        blank, count = re.subn(pattern, "_____", sentence, count=1, flags=re.I)
        if count:
            return blank
    clue = word.get("definition_en") or word["meaning_vi"]
    return f"_____ — {clue}"


def _new_question(kind: str, word: dict, words: list[dict], question_id: int) -> dict:
    if kind == "multiple_choice":
        answer = word["word"]
        return {
            "id": question_id,
            "kind": kind,
            "prompt": word["meaning_vi"],
            "choices": _choices(answer, [w["word"] for w in words]),
            "answer": answer,
        }
    if kind == "meaning":
        answer = word["meaning_vi"]
        choices = _choices(answer, [w["meaning_vi"] for w in words])
        if len(choices) > 1:
            return {
                "id": question_id,
                "kind": kind,
                "prompt": word["word"],
                "choices": choices,
                "answer": answer,
            }
    return {
        "id": question_id,
        "kind": "fill_blank",
        "prompt": _fill_prompt(word),
        "choices": None,
        "answer": word["word"],
    }


@router.post("", response_model=QuizStartOut, status_code=201)
def start_quiz(body: QuizStartIn, notebook: Notebook, quizzes: QuizRepo):
    words = notebook.list_words()
    if len(words) < 3:
        raise HTTPException(
            status_code=422, detail="Thêm ít nhất 3 từ vào sổ để tạo bài quiz."
        )
    random.shuffle(words)
    selected = words[: min(body.count, len(words))]
    kinds = ("multiple_choice", "fill_blank", "meaning")
    questions = [
        _new_question(kinds[index % len(kinds)], word, words, index + 1)
        for index, word in enumerate(selected)
    ]
    quiz_id = quizzes.create(questions)
    # The answer key is stored in the database, never in the response before submission.
    return {
        "quiz_id": quiz_id,
        "questions": [
            {key: value for key, value in question.items() if key != "answer"}
            for question in questions
        ],
    }


@router.post("/{quiz_id}/submit", response_model=QuizResult)
def submit_quiz(quiz_id: int, body: QuizSubmitIn, quizzes: QuizRepo):
    quiz = quizzes.get(quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài quiz")
    if quiz["submitted_at"] is not None:
        raise HTTPException(status_code=409, detail="Bài quiz này đã được chấm")

    submitted = {answer.question_id: answer.answer.strip() for answer in body.answers}
    questions = quiz["questions"]
    question_ids = {question["id"] for question in questions}
    if len(submitted) != len(body.answers) or set(submitted) != question_ids:
        raise HTTPException(status_code=422, detail="Cần trả lời đúng một lần cho mỗi câu hỏi")

    results = []
    for question in questions:
        answer = submitted[question["id"]]
        expected = question["answer"]
        results.append({
            **{key: value for key, value in question.items() if key != "answer"},
            "answer": answer,
            "expected": expected,
            "correct": answer.casefold() == expected.casefold(),
        })
    result = {
        "score": sum(item["correct"] for item in results),
        "total": len(results),
        "questions": results,
    }
    if not quizzes.finish(quiz_id, result):
        raise HTTPException(status_code=409, detail="Bài quiz này đã được chấm")
    return result

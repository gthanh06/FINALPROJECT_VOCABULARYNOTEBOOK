# tests/fake_ai.py — a stand-in for GeminiProvider: answers come from a queue the test fills.
import json

from app.ai.errors import AIRetryable


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.answers: list = []  # str (raw JSON), dict (dumped to JSON) or an exception
        self.calls: list[dict] = []
        self.sleeps: list[float] = []

    def queue(self, *answers) -> None:
        self.answers.extend(answers)

    def generate_json(self, system: str, prompt: str, schema: dict) -> str:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)


RATE_LIMITED = AIRetryable(429)


def lookup_answer(word="resilient", **changes) -> dict:
    """A valid answer to prompts/lookup.md."""
    return {
        "is_english_word": True,
        "suggestion": None,
        "word": word,
        "ipa": "/rɪˈzɪliənt/",
        "part_of_speech": "adjective",
        "meaning_vi": "kiên cường; mau phục hồi",
        "definition_en": "able to recover quickly from difficulties",
        "examples": [
            {"en": "Children are often very resilient.", "vi": "Trẻ em thường rất kiên cường."},
            {"en": "The economy proved resilient.", "vi": "Nền kinh tế tỏ ra vững vàng."},
        ],
        "synonyms": ["tough", "hardy"],
        "antonyms": ["fragile"],
        "collocations": ["remarkably resilient", "resilient to change"],
        "usage_note": "Thường đi với giới từ to: resilient to sth.",
        "topic": "animals",
        **changes,
    }


def sentence_answer(verdict="incorrect", **changes) -> dict:
    """A valid answer to prompts/check_sentence.md."""
    wrong = verdict != "correct"
    return {
        "uses_word": True,
        "verdict": verdict,
        "errors": [{
            "type": "grammar",
            "excerpt": "She resilient",
            "explanation_vi": "Thiếu động từ to be: cần 'She is resilient'.",
        }] if wrong else [],
        "word_form": "resilient",
        "corrected": "She is very resilient.",
        "better_version": None,
        "feedback_vi": "Ý hay! Chỉ cần thêm động từ to be." if wrong else "Câu rất tốt!",
        **changes,
    }


def suggest_answer(*words: str) -> dict:
    """A valid answer to prompts/suggest_words.md with these words."""
    return {"words": [{
        "word": w,
        "part_of_speech": "noun",
        "ipa": "/x/",
        "meaning_vi": f"nghĩa của {w}",
        "definition_en": f"definition of {w}",
        "example": {"en": f"I like the {w} a lot.", "vi": f"Tôi rất thích {w}."},
    } for w in words]}

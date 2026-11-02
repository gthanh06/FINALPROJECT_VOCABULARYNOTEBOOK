# app/ai/schemas.py — the JSON each prompt must answer with.
#
# The model is given model_json_schema() as its response schema (structured output),
# and the answer is validated again here: the API does not enforce limits such as
# min_length, and a model can still be wrong. Field descriptions are part of the schema
# the model reads, so they double as instructions.
from typing import Literal

from pydantic import BaseModel, Field

PartOfSpeech = Literal[
    "noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun", "phrase",
]


class ExampleOut(BaseModel):
    en: str = Field(min_length=3, max_length=300, description="English sentence.")
    vi: str = Field(min_length=2, max_length=300, description="Its Vietnamese translation.")


class WordLookup(BaseModel):
    is_english_word: bool = Field(
        description="false if the input is not a real English word or common phrase."
    )
    suggestion: str | None = Field(
        default=None, max_length=100,
        description="If is_english_word is false: the closest real English word, else null.",
    )
    word: str = Field(max_length=100, description="The word, correctly spelled, lower case.")
    ipa: str = Field(max_length=100, description="IPA between slashes, e.g. /rɪˈzɪliənt/.")
    part_of_speech: PartOfSpeech | None = None
    meaning_vi: str = Field(max_length=300, description="Short Vietnamese meaning(s).")
    definition_en: str = Field(max_length=500, description="Short English definition.")
    examples: list[ExampleOut] = Field(max_length=3, description="Exactly 2 examples.")
    synonyms: list[str] = Field(max_length=8)
    antonyms: list[str] = Field(max_length=8)
    collocations: list[str] = Field(max_length=8)
    usage_note: str | None = Field(default=None, max_length=500, description="Tip in Vietnamese.")
    topic: str | None = Field(default=None, description="One of the given topic slugs, or null.")

    def is_complete(self) -> bool:
        """A real word must come with a meaning and at least one example."""
        if not self.is_english_word:
            return True
        return bool(self.word.strip() and self.meaning_vi.strip() and self.examples)


ErrorType = Literal[
    "grammar", "word_usage", "spelling", "word_choice", "punctuation", "missing_word",
]


class SentenceError(BaseModel):
    type: ErrorType
    excerpt: str = Field(max_length=300, description="The wrong part, copied from the sentence.")
    explanation_vi: str = Field(min_length=3, max_length=500, description="In Vietnamese.")


class SentenceCheck(BaseModel):
    uses_word: bool = Field(description="The sentence contains the word or an inflected form.")
    verdict: Literal["correct", "minor_issues", "incorrect"]
    errors: list[SentenceError] = Field(max_length=5)
    word_form: str = Field(
        max_length=100, description="The form of the target word used in corrected, e.g. readers."
    )
    corrected: str = Field(min_length=1, max_length=400, description="Minimal fixes only.")
    better_version: str | None = Field(default=None, max_length=400)
    feedback_vi: str = Field(min_length=3, max_length=600, description="Short, in Vietnamese.")

    def is_complete(self) -> bool:
        """A sentence that is not "correct" must say what is wrong."""
        if self.verdict != "correct" and not self.errors and self.uses_word:
            return False
        return bool(self.corrected.strip() and self.feedback_vi.strip())


class SuggestedWord(BaseModel):
    word: str = Field(min_length=1, max_length=60, description="Lower case, correctly spelled.")
    part_of_speech: PartOfSpeech | None = None
    ipa: str = Field(max_length=100, description="IPA between slashes.")
    meaning_vi: str = Field(min_length=1, max_length=200, description="Short Vietnamese meaning.")
    definition_en: str = Field(max_length=300, description="Short, simple English definition.")
    example: ExampleOut


class WordSuggestions(BaseModel):
    words: list[SuggestedWord] = Field(max_length=15)

    def is_complete(self) -> bool:
        return len(self.words) >= 3

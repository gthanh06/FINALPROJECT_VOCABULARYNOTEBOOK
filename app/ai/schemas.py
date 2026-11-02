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

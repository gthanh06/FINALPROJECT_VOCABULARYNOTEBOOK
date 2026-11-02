# app/ai/service.py — the one entry point the routes use to ask the AI something.
#
#   ai = get_ai()                                   # None when no API key is set
#   result = ai.run("lookup", WordLookup, word="resilient", topics="...")
#
# run() renders prompts/<name>.md, asks the provider for JSON matching the Pydantic
# model, validates it, and:
#   - JSON that does not match the schema: asks once more, then AIBadOutput
#   - 429 / overload: waits RETRY_DELAYS between attempts, then AIBusy
#   - timeout: AITimeout at once (the user is already waiting)
import os
import time
from functools import cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai import prompts
from app.ai.errors import AIBadOutput, AIBusy, AIRetryable

M = TypeVar("M", bound=BaseModel)

RETRY_DELAYS = (1.0, 3.0)  # seconds before the 2nd and 3rd attempt after a 429
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class Provider(Protocol):
    name: str
    model: str

    def generate_json(self, system: str, prompt: str, schema: dict) -> str:
        """Returns the model's raw JSON text, or raises an app.ai.errors exception."""
        ...


class AIService:
    def __init__(self, provider: Provider, sleep=time.sleep):
        self.provider = provider
        self.sleep = sleep

    @property
    def model(self) -> str:
        return self.provider.model

    def prompt_version(self, name: str) -> str:
        return prompts.load(name).version

    def run(self, prompt_name: str, output: type[M], **values: object) -> M:
        system, user = prompts.render(prompt_name, **values)
        schema = output.model_json_schema()
        for attempt in (1, 2):
            text = self._generate(system, user, schema)
            try:
                result = output.model_validate_json(text)
                if getattr(result, "is_complete", lambda: True)():
                    return result
                problem = "incomplete answer"
            except ValidationError as err:
                problem = f"{err.error_count()} validation error(s)"
            print(f"ai {prompt_name}: attempt {attempt} rejected ({problem})")
        raise AIBadOutput

    def _generate(self, system: str, user: str, schema: dict) -> str:
        for delay in (*RETRY_DELAYS, None):
            try:
                return self.provider.generate_json(system, user, schema)
            except AIRetryable as err:
                print(f"ai busy ({err}), retry in {delay}s" if delay else f"ai busy ({err})")
                if delay is None:
                    raise AIBusy from err
                self.sleep(delay)
        raise AssertionError("unreachable")


@cache
def get_ai() -> AIService | None:
    """The app's AI service, or None when GEMINI_API_KEY is not set (AI turned off)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    from app.ai.gemini import GeminiProvider  # the SDK is only imported when AI is on

    provider = GeminiProvider(
        api_key=key,
        model=os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL,
        timeout=float(os.environ.get("GEMINI_TIMEOUT", "20")),
    )
    return AIService(provider)

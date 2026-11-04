# app/ai/gemini.py — Google Gemini through the official Google Gen AI SDK (google-genai).
#
# The only file that imports the SDK. It uses the Interactions API with structured
# output: the JSON schema is sent as response_format, so Gemini answers with JSON text.
# SDK errors are mapped onto app/ai/errors.py; AIService decides about retries.
from google import genai
from google.genai import _interactions as gx
from google.genai import types

from app.ai.errors import AIBusy, AIError, AIRetryable, AITimeout

# Worth trying again after a pause: quota / rate limit and temporary overload.
RETRYABLE_STATUS = {429, 500, 503}


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float):
        # The SDK retries 429 / 5xx by itself (4 requests per call). AIService already
        # retries with its own backoff, so the SDK's retries are turned off: 599 is a
        # status code no server sends, so "retry only on 599" means "never retry".
        no_retry = types.HttpRetryOptions(attempts=1, http_status_codes=[599])
        self.client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=no_retry)
        )
        self.model = model
        self.timeout = timeout

    def generate_json(self, system: str, prompt: str, schema: dict) -> str:
        try:
            interaction = self.client.interactions.create(
                model=self.model,
                system_instruction=system,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                },
                timeout=self.timeout,
            )
        except gx.APITimeoutError as err:
            raise AITimeout from err
        except gx.APIConnectionError as err:
            raise AIBusy(
                "Could not connect to the AI service. Please try again in a few minutes."
            ) from err
        except gx.APIStatusError as err:
            # The detail (it can name the project) goes to the logs, not to the browser.
            print(f"gemini error {err.status_code}: {str(err)[:300]}")
            if err.status_code in RETRYABLE_STATUS:
                raise AIRetryable(err.status_code) from err
            raise AIError() from err
        return interaction.output_text or ""

# app/ai/errors.py — what can go wrong with the AI, as friendly English messages.
# app/ai_routes.py turns each one into an HTTP answer with its status code.


class AIError(Exception):
    status_code = 502
    message = "The AI is having trouble. Please try again later."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class AINotConfigured(AIError):
    status_code = 503
    message = "AI is not enabled on the server (GEMINI_API_KEY is missing)."


class AIBusy(AIError):
    # The provider's quota (429) or a temporary overload, still failing after the retries.
    status_code = 503
    message = "The AI service is busy. Please try again in a few minutes."


class AITimeout(AIError):
    status_code = 504
    message = "The AI took too long to respond. Please try again."


class AIBadOutput(AIError):
    # The answer did not match the JSON schema, even after one retry.
    status_code = 502
    message = "The AI returned data in an invalid format. Please try again."


class AIRetryable(Exception):
    """Raised by a provider for errors worth retrying with backoff (429, 503)."""

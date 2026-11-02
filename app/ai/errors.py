# app/ai/errors.py — what can go wrong with the AI, as friendly Vietnamese messages.
# app/ai_routes.py turns each one into an HTTP answer with its status code.


class AIError(Exception):
    status_code = 502
    message = "AI đang gặp sự cố, vui lòng thử lại sau."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class AINotConfigured(AIError):
    status_code = 503
    message = "Tính năng AI chưa được bật trên máy chủ (thiếu GEMINI_API_KEY)."


class AIBusy(AIError):
    # The provider's quota (429) or a temporary overload, still failing after the retries.
    status_code = 503
    message = "Hệ thống AI đang bận, thử lại sau ít phút."


class AITimeout(AIError):
    status_code = 504
    message = "AI phản hồi quá lâu, vui lòng thử lại."


class AIBadOutput(AIError):
    # The answer did not match the JSON schema, even after one retry.
    status_code = 502
    message = "AI trả về dữ liệu không đúng định dạng, vui lòng thử lại."


class AIRetryable(Exception):
    """Raised by a provider for errors worth retrying with backoff (429, 503)."""

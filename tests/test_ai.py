import io
import json
import urllib.error

import pytest

from app import ai
from app.schemas import AiSuggestIn, AiSuggestion

SUGGESTION = {
    "ipa": "/rɪˈzɪliənt/",
    "part_of_speech": "adjective",
    "definition_en": "able to recover quickly",
    "examples": [{"en": "She is resilient.", "vi": "Cô ấy kiên cường."}],
    "synonyms": ["tough"],
    "antonyms": ["fragile"],
    "collocations": ["resilient community"],
    "usage_note": "resilient to change",
}


def response(payload):
    return io.BytesIO(json.dumps(payload).encode())


def gemini_response(suggestion):
    return response(
        {"candidates": [{"content": {"parts": [{"text": json.dumps(suggestion)}]}}]}
    )


def suggest_input():
    return AiSuggestIn(word="resilient", meaning_vi="kiên cường")


def test_suggest_calls_gemini_and_parses_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        ai.urllib.request,
        "urlopen",
        lambda request, timeout: gemini_response(SUGGESTION),
    )
    result = ai.suggest(suggest_input())
    assert result == AiSuggestion.model_validate(SUGGESTION)


def test_missing_api_key_is_reported_without_request(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ai.AIConfigurationError):
        ai.suggest(suggest_input())


def test_rate_limit_retries_then_returns_busy_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai.time, "sleep", lambda _: None)
    calls = 0

    def rate_limited(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            "https://example.test", 429, "rate limited", {"Retry-After": "0"}, None
        )

    monkeypatch.setattr(ai.urllib.request, "urlopen", rate_limited)
    with pytest.raises(ai.AIRateLimitError):
        ai.suggest(suggest_input())
    assert calls == ai.MAX_ATTEMPTS


def test_timeout_retries_then_returns_timeout_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai.time, "sleep", lambda _: None)
    calls = 0

    def timed_out(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr(ai.urllib.request, "urlopen", timed_out)
    with pytest.raises(ai.AITimeoutError):
        ai.suggest(suggest_input())
    assert calls == ai.MAX_ATTEMPTS


def test_empty_response_retries_then_returns_provider_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai.time, "sleep", lambda _: None)
    calls = 0

    def empty(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response({"candidates": []})

    monkeypatch.setattr(ai.urllib.request, "urlopen", empty)
    with pytest.raises(ai.AIServiceError) as error:
        ai.suggest(suggest_input())
    assert type(error.value) is ai.AIServiceError
    assert calls == ai.MAX_ATTEMPTS


def test_ai_suggest_endpoint_requires_login(anon):
    assert anon.post(
        "/api/notebook/ai-suggest",
        json={"word": "resilient", "meaning_vi": "kiên cường"},
    ).status_code == 401


def test_ai_suggest_endpoint_returns_suggestion(learner, monkeypatch):
    monkeypatch.setattr(ai, "suggest", lambda _: AiSuggestion.model_validate(SUGGESTION))
    result = learner.post(
        "/api/notebook/ai-suggest",
        json={"word": "resilient", "meaning_vi": "kiên cường"},
    )
    assert result.status_code == 200
    assert result.json() == SUGGESTION


def test_ai_suggest_endpoint_reports_provider_errors(learner, monkeypatch):
    def unavailable(_):
        raise ai.AIRateLimitError

    monkeypatch.setattr(ai, "suggest", unavailable)
    result = learner.post(
        "/api/notebook/ai-suggest",
        json={"word": "resilient", "meaning_vi": "kiên cường"},
    )
    assert result.status_code == 503
    assert result.json()["detail"] == ai.AIRateLimitError.detail

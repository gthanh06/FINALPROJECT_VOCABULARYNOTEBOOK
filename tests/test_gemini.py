# tests/test_gemini.py — GeminiProvider against a local fake HTTP server (no real Gemini call).
# Checks how SDK errors are mapped, and that one call sends exactly one request
# (the SDK's own retries are off; AIService does the retrying).
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from google.genai import types

from app.ai.errors import AIError, AIRetryable, AITimeout
from app.ai.gemini import GeminiProvider


@pytest.fixture
def server():
    """A local server that answers every POST with (status, delay) taken from `reply`."""
    state = {"reply": (200, 0), "hits": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["hits"] += 1
            self.rfile.read(int(self.headers.get("content-length", 0)))
            status, delay = state["reply"]
            time.sleep(delay)
            body = json.dumps({"error": {"code": status, "message": "test", "status": "X"}})
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_port}/"
    yield state
    srv.shutdown()


def provider(server, timeout=5.0):
    p = GeminiProvider(api_key="test-key-not-real", model="gemini-test", timeout=timeout)
    # Same client settings, pointed at the local server.
    options = p.client._api_client._http_options
    p.client = type(p.client)(
        api_key="test-key-not-real",
        http_options=types.HttpOptions(base_url=server["url"], retry_options=options.retry_options),
    )
    return p


@pytest.mark.parametrize("status", [429, 503])
def test_busy_is_retryable_and_sent_once(server, status):
    server["reply"] = (status, 0)
    with pytest.raises(AIRetryable):
        provider(server).generate_json("system", "prompt", {"type": "object"})
    assert server["hits"] == 1


def test_bad_request_is_a_plain_error(server):
    server["reply"] = (400, 0)
    with pytest.raises(AIError) as err:
        provider(server).generate_json("system", "prompt", {"type": "object"})
    assert not isinstance(err.value, AITimeout)
    assert server["hits"] == 1


def test_slow_answer_is_a_timeout(server):
    server["reply"] = (200, 2)
    with pytest.raises(AITimeout):
        provider(server, timeout=0.3).generate_json("system", "prompt", {"type": "object"})
    assert server["hits"] == 1

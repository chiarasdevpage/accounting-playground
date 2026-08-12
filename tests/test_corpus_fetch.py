"""The HTTP layer, driven entirely through a mock transport.

Nothing here reaches the internet: `httpx.MockTransport` answers every request
from a script, which is what lets the retry and timeout behaviour be tested at
all — a real flaky network cannot be asked to fail on demand.
"""

from __future__ import annotations

import httpx
import pytest

from apg.corpus import fetch


def client_for(handler) -> httpx.Client:
    return fetch.make_client(transport=httpx.MockTransport(handler))


def test_a_successful_page_comes_back_as_text():
    with client_for(lambda request: httpx.Response(200, text="<html>hi</html>")) as c:
        assert fetch.get(c, "https://example.invalid/x") == "<html>hi</html>"


def test_the_user_agent_identifies_the_project():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, text="ok")

    with client_for(handler) as c:
        fetch.get(c, "https://example.invalid/x")

    assert "accounting-playground" in seen["ua"]
    assert "accounting-playground" in fetch.USER_AGENT


def test_a_server_error_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, text="finally")

    with client_for(handler) as c:
        got = fetch.get(c, "https://example.invalid/x", sleep=lambda s: None)
    assert got == "finally"
    assert calls["n"] == 3


def test_a_timeout_is_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("too slow", request=request)
        return httpx.Response(200, text="ok")

    with client_for(handler) as c:
        assert fetch.get(c, "https://example.invalid/x", sleep=lambda s: None) == "ok"
    assert calls["n"] == 2


def test_a_missing_page_is_not_retried():
    """A 404 means the URL is wrong; asking four more times cannot fix that."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    with client_for(handler) as c, pytest.raises(httpx.HTTPStatusError):
        fetch.get(c, "https://example.invalid/missing", sleep=lambda s: None)
    assert calls["n"] == 1


def test_giving_up_raises_the_last_error():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with client_for(handler) as c, pytest.raises(httpx.ConnectError):
        fetch.get(c, "https://example.invalid/x", sleep=lambda s: None)


def test_retries_back_off_rather_than_hammering():
    waits = []

    def handler(request):
        return httpx.Response(500)

    with client_for(handler) as c, pytest.raises(httpx.HTTPStatusError):
        fetch.get(c, "https://example.invalid/x", sleep=waits.append)

    assert len(waits) == fetch.MAX_ATTEMPTS - 1
    assert waits == sorted(waits), "each wait should be longer than the last"


def test_sha256_is_stable_and_content_dependent():
    assert fetch.sha256("abc") == fetch.sha256("abc")
    assert fetch.sha256("abc") != fetch.sha256("abd")
    assert len(fetch.sha256("abc")) == 64

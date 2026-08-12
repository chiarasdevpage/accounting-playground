"""Getting pages from pcaobus.org, politely.

Plain-English picture: 51 pages, one at a time, with a short pause between them
and a few retries if the network hiccups. It takes about a minute.

Sequential and slightly slow is the deliberate choice. Firing 51 parallel
requests at a regulator's website to save forty seconds would be rude, and this
download happens once per corpus version — the pinning rules mean re-running it
is the exception, not the routine. `pcaobus.org/robots.txt` permits this
(its rule set is an empty `Disallow:`), and the User-Agent below says who we are
so their operators can see what we're doing.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

import httpx

from apg import __version__

USER_AGENT = (
    f"accounting-playground/{__version__} "
    "(research corpus builder; https://github.com/ProjectBuilder67/accounting-playground)"
)

TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3
DELAY_SECONDS = 0.5
"""Pause between successive requests. Not required by the site; just good manners."""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """The configured client. `transport` is the seam the tests inject through."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        transport=transport,
    )


def get(
    client: httpx.Client,
    url: str,
    attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Fetch one page as text, retrying transient failures with a growing backoff.

    A 404 or other 4xx is not retried — the URL is wrong and trying again will
    not fix it. Timeouts, connection errors and 5xx are retried, since those are
    usually the network having a bad moment.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url)
            if 400 <= response.status_code < 500:
                response.raise_for_status()
            if response.status_code >= 500:
                response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise
            last = exc
        except httpx.HTTPError as exc:
            last = exc

        if attempt < attempts:
            sleep(DELAY_SECONDS * 2**attempt)

    assert last is not None  # only reachable after a failed attempt
    raise last


__all__ = [
    "DELAY_SECONDS",
    "MAX_ATTEMPTS",
    "TIMEOUT_SECONDS",
    "USER_AGENT",
    "get",
    "make_client",
    "sha256",
]

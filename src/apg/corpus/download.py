"""The download, start to finish.

Plain-English picture: read the index, fetch each standard, parse it, save it,
then write the manifest. This is the only place that knows the whole sequence.

It reports progress through a callback rather than printing anything itself. The
corpus package stays free of Rich, Typer and `Session`, which is what lets the
parser and the store be tested as ordinary functions — and what would let a
future phase run the same download from a notebook or a script.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from apg import paths
from apg.corpus import fetch, source, store
from apg.corpus.model import Standard
from apg.corpus.parse import ParseError, parse_standard
from apg.corpus.source import StandardRef

ProgressFn = Callable[[int, int, StandardRef], None]
"""Called before each fetch with (index, total, ref). `index` is 1-based."""


@dataclass
class DownloadResult:
    version: str
    root: Path
    standards: list[Standard] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def paragraph_count(self) -> int:
        return sum(s.paragraph_count for s in self.standards)


def read_index(
    client: httpx.Client,
    index_url: str = source.INDEX_URL,
) -> list[StandardRef]:
    """The list of standards to fetch.

    Separate from `fetch_all` so a caller can know the count before starting —
    a progress bar needs its total up front, and the total is only knowable after
    this page has been read.
    """
    refs = source.parse_index(fetch.get(client, index_url), base_url=index_url)
    if not refs:
        raise ParseError(
            "the standards index listed no standards - the site layout may have changed"
        )
    return refs


def fetch_all(
    client: httpx.Client,
    refs: list[StandardRef],
    version: str | None = None,
    on_progress: ProgressFn | None = None,
    sleep: Callable[[float], None] = time.sleep,
    index_url: str = source.INDEX_URL,
) -> DownloadResult:
    """Fetch, parse and save each standard in `refs`, then write the manifest.

    One standard failing does not abandon the other fifty. Failures are collected
    and returned so the command can report them; a corpus that is short a few
    standards is still useful, but it must never be presented as complete.
    """
    resolved = version or store.default_version()
    root = paths.corpus_version_dir(resolved)
    result = DownloadResult(version=resolved, root=root)

    for position, ref in enumerate(refs, start=1):
        if on_progress is not None:
            on_progress(position, len(refs), ref)
        try:
            html = fetch.get(client, ref.url)
            standard = parse_standard(
                html,
                url=ref.url,
                source_sha256=fetch.sha256(html),
                fetched_utc=store.utc_now(),
            )
            store.save_standard(root, standard, html)
            result.standards.append(standard)
        except (httpx.HTTPError, ParseError, ValueError) as exc:
            result.failures.append((ref.as_number, str(exc)))

        if position < len(refs):
            sleep(fetch.DELAY_SECONDS)

    if result.standards:
        result.manifest = store.save_manifest(
            root, resolved, result.standards, index_url
        )
    return result


def download(
    version: str | None = None,
    on_progress: ProgressFn | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    index_url: str = source.INDEX_URL,
) -> DownloadResult:
    """Read the index and fetch everything on it — the whole job in one call."""
    owned = client is None
    http = client or fetch.make_client()
    try:
        refs = read_index(http, index_url)
        return fetch_all(
            http,
            refs,
            version=version,
            on_progress=on_progress,
            sleep=sleep,
            index_url=index_url,
        )
    finally:
        if owned:
            http.close()


__all__ = ["DownloadResult", "ProgressFn", "download", "fetch_all", "read_index"]

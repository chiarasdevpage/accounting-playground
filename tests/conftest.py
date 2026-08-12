"""Shared test fixtures.

Two rules hold across the whole suite and are enforced from here:

* **No test touches the network.** The corpus fixtures below are real pages saved
  to disk, so the parser is checked against genuine PCAOB markup rather than a
  tidy invention that would never catch the site's quirks.
* **No test touches the real corpus.** `APG_DATA_DIR` is redirected to a
  temporary directory for every test, so running the suite can neither read a
  corpus the developer downloaded nor scribble on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point `apg.paths` at a throwaway directory for the duration of each test."""
    monkeypatch.setenv("APG_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def as2301_html() -> str:
    """A long standard: 23 sections, an appendix, 29 footnotes, lists and Notes."""
    return (FIXTURES / "as2301.html").read_text(encoding="utf-8")


@pytest.fixture
def as3110_html() -> str:
    """A short standard, for the case where there is barely any structure."""
    return (FIXTURES / "as3110.html").read_text(encoding="utf-8")


@pytest.fixture
def as1110_html() -> str:
    """A standard with no headings at all — paragraphs sit straight under the title.

    Four of the 51 standards look like this, and an earlier parser dropped every
    one of them silently. That is exactly the failure this fixture exists to
    catch: the download still "succeeded", just with 8% of the corpus missing.
    """
    return (FIXTURES / "as1110.html").read_text(encoding="utf-8")


@pytest.fixture
def index_html() -> str:
    """The standards index, with all 51 links and both URL-slug styles."""
    return (FIXTURES / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def built_corpus(as2301_html, as3110_html):
    """A tiny two-standard corpus on disk, complete with manifest.

    Built through the real `store` functions rather than hand-written JSON, so
    the command tests exercise the same files a genuine download produces.
    """
    from apg.corpus import fetch, store
    from apg.corpus.parse import parse_standard

    version = "2026-08"
    root = None
    standards = []
    for html, url in (
        (as2301_html, "https://example.invalid/AS2301"),
        (as3110_html, "https://example.invalid/AS3110"),
    ):
        standard = parse_standard(
            html,
            url=url,
            source_sha256=fetch.sha256(html),
            fetched_utc="2026-08-11T00:00:00Z",
        )
        from apg import paths

        root = paths.corpus_version_dir(version)
        store.save_standard(root, standard, html)
        standards.append(standard)

    store.save_manifest(root, version, standards, "https://example.invalid/index")
    return store.load_corpus(version)

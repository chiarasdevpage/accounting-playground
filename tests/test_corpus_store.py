"""Saving the corpus, and the manifest that pins it."""

from __future__ import annotations

import json

import httpx
import pytest

from apg import paths
from apg.corpus import download as downloader
from apg.corpus import fetch, store
from apg.corpus.model import Standard
from apg.corpus.parse import parse_standard


def test_a_saved_standard_produces_all_three_files(built_corpus):
    root = built_corpus.root
    assert (root / "raw" / "AS2301.html").is_file()
    assert (root / "json" / "AS2301.json").is_file()
    assert (root / "text" / "AS2301.txt").is_file()


def test_a_standard_round_trips_through_disk(built_corpus, as2301_html):
    original = parse_standard(as2301_html, url="https://example.invalid/AS2301")
    loaded = built_corpus.load("AS 2301")
    assert loaded.as_number == original.as_number
    assert loaded.paragraph_count == original.paragraph_count
    assert loaded.sections == original.sections


def test_a_standard_can_be_loaded_however_the_number_is_typed(built_corpus):
    assert built_corpus.load("2301").as_number == "AS 2301"
    assert built_corpus.load("as2301").as_number == "AS 2301"


def test_the_manifest_records_what_was_downloaded(built_corpus):
    manifest = built_corpus.manifest
    assert manifest["corpus"] == store.CORPUS_NAME
    assert manifest["version"] == "2026-08"
    assert manifest["standard_count"] == 2
    assert manifest["downloaded_utc"].endswith("Z")
    assert manifest["fingerprint"].startswith("sha256:")
    assert manifest["apg_version"]


def test_the_manifest_states_the_effective_date_limitation(built_corpus):
    """An undated snapshot implies a permanence the standards do not have."""
    notes = " ".join(built_corpus.manifest["notes"])
    assert "effective date" in notes
    assert "not professional audit or tax advice" in notes


def test_every_standard_has_a_checksum(built_corpus):
    for entry in built_corpus.entries:
        assert len(entry["sha256"]) == 64
        assert entry["paragraphs"] > 0
        assert entry["url"]


def test_the_fingerprint_is_stable_across_runs(as2301_html):
    made = [
        Standard(
            as_number="AS 2301",
            title="t",
            url="u",
            source_sha256=fetch.sha256(as2301_html),
        )
    ]
    assert store.fingerprint(made) == store.fingerprint(made)


def test_the_fingerprint_ignores_the_order_it_is_given():
    a = Standard(as_number="AS 1000", title="t", url="u", source_sha256="aa")
    b = Standard(as_number="AS 2301", title="t", url="u", source_sha256="bb")
    assert store.fingerprint([a, b]) == store.fingerprint([b, a])


def test_the_fingerprint_changes_when_the_source_text_changes():
    a = Standard(as_number="AS 1000", title="t", url="u", source_sha256="aa")
    moved = Standard(as_number="AS 1000", title="t", url="u", source_sha256="zz")
    assert store.fingerprint([a]) != store.fingerprint([moved])


def test_no_corpus_reads_as_none():
    assert store.load_corpus() is None
    assert paths.latest_corpus_version() is None


def test_a_directory_without_a_manifest_is_not_a_corpus():
    """A download killed half way leaves files behind; that is not a pinned corpus."""
    half_done = paths.corpus_version_dir("2026-01")
    (half_done / "json").mkdir(parents=True)
    assert paths.latest_corpus_version() is None
    assert store.load_corpus() is None


def test_the_newest_version_is_the_one_reported(built_corpus):
    older = paths.corpus_version_dir("2025-01")
    older.mkdir(parents=True, exist_ok=True)
    (older / store.MANIFEST_NAME).write_text(json.dumps({"version": "2025-01"}))
    assert paths.latest_corpus_version() == "2026-08"


def test_text_files_use_unix_line_endings(built_corpus):
    """Otherwise every checksum would depend on which OS did the download."""
    raw = (built_corpus.root / "text" / "AS2301.txt").read_bytes()
    assert b"\r\n" not in raw


def test_reparse_rebuilds_from_saved_html_without_the_network(built_corpus):
    """The reason raw pages are kept: fix the parser, rebuild in seconds."""
    rebuilt = store.reparse(built_corpus.version)
    assert {s.as_number for s in rebuilt} == {"AS 2301", "AS 3110"}

    after = store.load_corpus(built_corpus.version)
    assert after.fingerprint == built_corpus.fingerprint, (
        "re-parsing must not move the fingerprint - the source text did not change"
    )


def test_data_dir_honours_the_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("APG_DATA_DIR", str(tmp_path / "elsewhere"))
    assert paths.data_dir() == tmp_path / "elsewhere"


def test_download_writes_a_complete_corpus(as2301_html, index_html):
    """The whole pipeline end to end, with the website replaced by a script."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("auditing-standards"):
            return httpx.Response(200, text=index_html)
        return httpx.Response(200, text=as2301_html)

    client = fetch.make_client(transport=httpx.MockTransport(handler))
    result = downloader.download(client=client, sleep=lambda s: None)

    # Every page answers with AS 2301, so 51 refs collapse to one saved standard;
    # what matters is that the index drove the run and the manifest was written.
    assert result.standards
    assert result.manifest["fingerprint"].startswith("sha256:")
    assert store.load_corpus() is not None


def test_a_single_bad_page_does_not_abandon_the_rest(as2301_html):
    """Fifty good standards are worth keeping; the failure is reported, not fatal."""
    base = "https://x.invalid/oversight/standards/auditing-standards/details"
    index = (
        "<ul>"
        f'<li><a href="{base}/AS2301">AS 2301: Good</a></li>'
        f'<li><a href="{base}/AS3110">AS 3110: Bad</a></li>'
        "</ul>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/index"):
            return httpx.Response(200, text=index)
        if "AS3110" in str(request.url):
            return httpx.Response(200, text="<html>not a standard</html>")
        return httpx.Response(200, text=as2301_html)

    client = fetch.make_client(transport=httpx.MockTransport(handler))
    result = downloader.download(
        client=client, sleep=lambda s: None, index_url="https://x.invalid/index"
    )

    assert [s.as_number for s in result.standards] == ["AS 2301"]
    assert [n for n, _ in result.failures] == ["AS 3110"]


def test_an_empty_index_is_an_error_not_an_empty_corpus():
    """Silently writing a corpus of nothing would be the worst possible outcome."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>site redesigned</html>")

    client = fetch.make_client(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="listed no standards"):
        downloader.download(
            client=client, sleep=lambda s: None, index_url="https://x.invalid/index"
        )

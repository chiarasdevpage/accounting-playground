"""Writing the corpus to disk, and the manifest that pins it.

Plain-English picture: each standard is saved three ways — the original page
exactly as the server sent it, a structured `.json` for the machine, and a
readable `.txt` for you. Alongside them sits `manifest.json`, which records what
was downloaded, when, and a checksum of every file.

The manifest is the point of this module. "Pin everything" is a project ground
rule, and a corpus you cannot prove is unchanged is not pinned — every score the
bench produces would rest on an assumption nobody checked. The `fingerprint`
field reduces the whole corpus to one string: if two runs report the same
fingerprint they read exactly the same text, and if they differ the corpus moved
and the comparison is void.

Keeping the raw HTML is what makes the parser fixable. A parsing bug found in
Phase 3 can be corrected and re-run over the saved pages in seconds, without
going back to pcaobus.org and without any risk that the site changed in between.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apg import __version__, paths
from apg.corpus.model import Standard, as_slug, normalize_as_number
from apg.corpus.parse import parse_standard

MANIFEST_NAME = "manifest.json"
CORPUS_NAME = "PCAOB Auditing Standards"

# Recorded in every manifest. PCAOB phases amendments in by fiscal year, so the
# pages carry whatever text is effective on the day they are read; that is a
# property of the corpus, and the honest thing is to state it rather than imply
# the snapshot is timeless.
STANDING_NOTES = (
    "Text as published on pcaobus.org on the download date.",
    "PCAOB phases amendments in by effective date; this snapshot is not "
    "guaranteed to match any other fiscal year's version of the standards.",
    "Research/education artifact - not professional audit or tax advice.",
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_version() -> str:
    """Corpus versions are named for the month they were downloaded: `2026-08`."""
    return datetime.now(UTC).strftime("%Y-%m")


def fingerprint(standards: list[Standard]) -> str:
    """One checksum standing for the whole corpus.

    Built from the per-page checksums rather than the parsed output, so it pins
    the source text: a parser improvement leaves the fingerprint alone, which is
    correct — the corpus did not change, only our reading of it.
    """
    digest = hashlib.sha256()
    for std in sorted(standards, key=lambda s: s.as_number):
        digest.update(f"{std.as_number} {std.source_sha256}\n".encode())
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True)
class Corpus:
    """A downloaded corpus, read back from disk."""

    version: str
    root: Path
    manifest: dict[str, Any]

    @property
    def downloaded_utc(self) -> str:
        return self.manifest.get("downloaded_utc", "")

    @property
    def fingerprint(self) -> str:
        return self.manifest.get("fingerprint", "")

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self.manifest.get("standards", []))

    @property
    def standard_count(self) -> int:
        return len(self.entries)

    @property
    def paragraph_count(self) -> int:
        return sum(int(e.get("paragraphs", 0)) for e in self.entries)

    def json_path(self, as_number: str) -> Path:
        return self.root / "json" / f"{as_slug(as_number)}.json"

    def text_path(self, as_number: str) -> Path:
        return self.root / "text" / f"{as_slug(as_number)}.txt"

    def has(self, as_number: str) -> bool:
        return self.json_path(as_number).is_file()

    def load(self, as_number: str) -> Standard:
        """One standard, read back into a `Standard`. Raises FileNotFoundError."""
        canonical = normalize_as_number(as_number)
        raw = json.loads(self.json_path(canonical).read_text(encoding="utf-8"))
        return Standard.from_dict(raw)

    def load_all(self) -> list[Standard]:
        """Every standard, in AS-number order. Used by `corpus search`."""
        return [self.load(entry["as_number"]) for entry in self.entries]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" so the corpus is byte-identical on Windows and Linux; without
    # it every checksum computed here would depend on the operating system.
    path.write_text(text, encoding="utf-8", newline="\n")


def save_standard(root: Path, standard: Standard, raw_html: str) -> None:
    """Write one standard's three files."""
    _write(root / "raw" / f"{standard.slug}.html", raw_html)
    _write(
        root / "json" / f"{standard.slug}.json",
        json.dumps(standard.to_dict(), indent=2, ensure_ascii=False) + "\n",
    )
    _write(root / "text" / f"{standard.slug}.txt", standard.to_text())


def save_manifest(
    root: Path,
    version: str,
    standards: list[Standard],
    source_index: str,
) -> dict[str, Any]:
    """Write `manifest.json` and return it."""
    manifest = {
        "corpus": CORPUS_NAME,
        "version": version,
        "downloaded_utc": utc_now(),
        "source_index": source_index,
        "apg_version": __version__,
        "standard_count": len(standards),
        "paragraph_count": sum(s.paragraph_count for s in standards),
        "fingerprint": fingerprint(standards),
        "notes": list(STANDING_NOTES),
        "standards": [
            {
                "as_number": s.as_number,
                "title": s.title,
                "series": s.series,
                "url": s.url,
                "sha256": s.source_sha256,
                "sections": len(s.sections),
                "paragraphs": s.paragraph_count,
                "footnotes": len(s.footnotes),
            }
            for s in sorted(standards, key=lambda s: s.as_number)
        ],
    }
    _write(root / MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def load_corpus(version: str | None = None) -> Corpus | None:
    """Read a downloaded corpus, or None if there isn't one.

    Returning None rather than raising: "no corpus yet" is the expected state on a
    fresh clone, and the commands turn it into a one-line "run `corpus download`"
    message instead of an error about a missing file.
    """
    resolved = version or paths.latest_corpus_version()
    if resolved is None:
        return None
    root = paths.corpus_version_dir(resolved)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return Corpus(version=resolved, root=root, manifest=manifest)


def reparse(version: str) -> list[Standard]:
    """Re-run the parser over saved HTML, without touching the network.

    This is why the raw pages are kept: when the parser improves, the corpus can
    be rebuilt from disk in seconds and the fingerprint stays put, proving the
    source text did not move.
    """
    root = paths.corpus_version_dir(version)
    corpus = load_corpus(version)
    if corpus is None:
        raise FileNotFoundError(f"no corpus version {version!r} on disk")

    rebuilt: list[Standard] = []
    for entry in corpus.entries:
        raw_path = root / "raw" / f"{as_slug(entry['as_number'])}.html"
        html = raw_path.read_text(encoding="utf-8")
        standard = parse_standard(
            html,
            url=entry["url"],
            source_sha256=entry["sha256"],
            fetched_utc=corpus.downloaded_utc,
        )
        save_standard(root, standard, html)
        rebuilt.append(standard)

    save_manifest(root, version, rebuilt, corpus.manifest.get("source_index", ""))
    return rebuilt


__all__ = [
    "CORPUS_NAME",
    "MANIFEST_NAME",
    "STANDING_NOTES",
    "Corpus",
    "default_version",
    "fingerprint",
    "load_corpus",
    "reparse",
    "save_manifest",
    "save_standard",
    "utc_now",
]

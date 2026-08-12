"""Where the app keeps things on disk.

Plain-English picture: downloaded standards, generated datasets and model files
are large, reproducible, and never committed to git. They all live under one
`data/` directory next to the project, and this module is the only thing that
decides where that is. Nothing else in the app builds a path by hand.

`APG_DATA_DIR` overrides the location, which is what the test suite uses to keep
its scribbles inside a temporary directory instead of the real corpus.
"""

from __future__ import annotations

import os
from pathlib import Path

CORPUS_DIRNAME = "corpus"


def project_root() -> Path:
    """The repository root — the directory holding `pyproject.toml`.

    Walks up from this file. When the package is installed somewhere without the
    project alongside it (a plain `pip install`, say) there is no repo to find,
    so we fall back to a per-user directory rather than writing gigabytes into
    site-packages.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.home() / ".apg"


def data_dir() -> Path:
    override = os.environ.get("APG_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return project_root() / "data"


def corpus_dir() -> Path:
    """Holds one subdirectory per downloaded corpus version."""
    return data_dir() / CORPUS_DIRNAME


def corpus_version_dir(version: str) -> Path:
    return corpus_dir() / version


def corpus_versions() -> list[str]:
    """Every downloaded corpus version, oldest first.

    Only directories carrying a `manifest.json` count: a download that died
    half-way leaves files behind, and a corpus without its manifest is not a
    pinned corpus and must not be reported as one.
    """
    root = corpus_dir()
    if not root.is_dir():
        return []
    found = [
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and (entry / "manifest.json").is_file()
    ]
    return sorted(found)


def latest_corpus_version() -> str | None:
    """The newest downloaded version, or None if there is no corpus yet.

    Called by the status strip on every keystroke-driven redraw, so it must never
    raise — an unreadable data directory reports "nothing downloaded", which is
    both true enough and better than crashing the prompt.
    """
    try:
        versions = corpus_versions()
    except OSError:
        return None
    return versions[-1] if versions else None


__all__ = [
    "corpus_dir",
    "corpus_version_dir",
    "corpus_versions",
    "data_dir",
    "latest_corpus_version",
    "project_root",
]

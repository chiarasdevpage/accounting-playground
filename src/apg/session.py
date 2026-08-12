"""The session — global flags plus whatever the app currently has loaded.

Plain-English picture: one object, created once when the app starts, passed to
every command. It carries the flags you typed (`--json`, `--quiet`, ...) and the
state the status strip reports.

The state fields matter more than they look. Later phases load a fine-tuned model
and answer many questions against it; loading takes real time, so the model must
live somewhere that survives between commands. That "somewhere" is this object,
which is why the interactive shell is the primary surface and one-shot CLI calls
are a secondary entry point into the same functions.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from rich.console import Console

import apg.console  # noqa: F401 - imported for its UTF-8 console setup side effect

_UNSET = "<unset>"
"""Sentinel for "not looked up yet", distinct from a genuine None result."""


@dataclass
class Session:
    """Resolved once at startup and passed down to every command."""

    # Global flags.
    json_out: bool = False
    quiet: bool = False
    no_color: bool = False
    debug: bool = False

    # Live state, reported by `status` and the REPL's status strip.
    # All empty in Phase 1 — there is no corpus, dataset, or model yet.
    active_specialist: str | None = None
    corpus_version: str | None = None
    dataset_counts: dict[str, int] = field(default_factory=dict)

    # Cache for `detected_corpus_version`. `_UNSET` rather than None because
    # "we looked and found nothing" and "we have not looked yet" are different
    # states, and only the second one should trigger a disk read.
    _detected_corpus: str | None = _UNSET

    @property
    def console(self) -> Console:
        # no_color strips ANSI styling; quiet additionally implies no colour so
        # that piped and CI output is plain text either way.
        #
        # markup=False is a safety property, not a style choice. Everything here
        # is styled through Rich's `style=` argument, never inline tags, so
        # disabling markup costs nothing — and it stops text we print from being
        # reinterpreted as formatting. Without it, `usage: help [command]` loses
        # its brackets and an unknown command containing `[` crashes the render.
        return Console(
            no_color=self.no_color or self.quiet,
            highlight=False,
            soft_wrap=True,
            markup=False,
        )

    @property
    def mascot_enabled(self) -> bool:
        """Tick appears only for an interactive human who hasn't opted out."""
        if self.json_out or self.quiet:
            return False
        if os.environ.get("APG_NO_MASCOT"):
            return False
        return sys.stdout.isatty()

    def detected_corpus_version(self) -> str | None:
        """The newest corpus on disk, looked up once and remembered.

        Nothing loads the corpus at startup — that would put a disk read in front
        of every `apg --help` — so the version is discovered lazily the first time
        anything asks what is loaded. Cached because the status strip re-renders
        on every keystroke, and guarded because a redraw must never be able to
        crash the prompt.
        """
        if self._detected_corpus is _UNSET:
            from apg import paths

            try:
                self._detected_corpus = paths.latest_corpus_version()
            except Exception:  # noqa: BLE001 - a decoration must not break the shell
                self._detected_corpus = None
        return self._detected_corpus

    def state_summary(self) -> dict[str, object]:
        """The three facts the status strip and `status` both report.

        Both readers go through this so the strip and the table can never
        disagree about what is loaded.
        """
        total = sum(self.dataset_counts.values())
        return {
            "specialist": self.active_specialist,
            # An explicitly set version wins, so tests and future phases can
            # pin the session to one corpus without touching the disk.
            "corpus_version": self.corpus_version or self.detected_corpus_version(),
            "dataset_pairs": total,
        }

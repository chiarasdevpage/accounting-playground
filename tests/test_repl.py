"""The shell's parts, tested without a terminal.

The loop itself needs a real TTY and is checked by hand (see README / the phase
checklist). Everything around it — the strip, the completer, the banner, and the
non-interactive fallback — is ordinary code and tested here.
"""

from __future__ import annotations

from prompt_toolkit.document import Document

from apg.repl import RegistryCompleter, banner, print_help_plain, start, status_strip
from apg.session import Session


def completions(text: str) -> list[str]:
    doc = Document(text, len(text))
    return [c.text for c in RegistryCompleter().get_completions(doc, None)]


def test_completion_is_driven_by_the_registry():
    """Completing `st` must offer `status` — with no hand-maintained word list."""
    assert completions("st") == ["status"]


def test_completion_offers_everything_on_an_empty_line():
    from apg.registry import REGISTRY

    assert set(completions("")) == set(REGISTRY)


def test_completion_does_not_suggest_an_already_complete_word():
    assert "status" not in completions("status")


def test_status_strip_reports_empty_state():
    strip = status_strip(Session())
    assert "specialist: none" in strip
    assert "corpus: not downloaded" in strip
    assert "pairs: 0" in strip


def test_status_strip_reflects_loaded_state():
    """The strip must track the session, since later phases load a model into it."""
    session = Session(
        active_specialist="qwen-audit",
        corpus_version="2026-08",
        dataset_counts={"recall": 1200, "application": 800},
    )
    strip = status_strip(session)
    assert "specialist: qwen-audit" in strip
    assert "corpus: 2026-08" in strip
    assert "pairs: 2000" in strip


def test_strip_and_status_command_read_the_same_source():
    """One source of truth: the strip cannot drift from what `status` reports."""
    session = Session(active_specialist="qwen-audit")
    assert session.state_summary()["specialist"] in status_strip(session)


def test_banner_renders(capsys):
    banner(Session(quiet=True))
    out = capsys.readouterr().out
    assert "accounting playground" in out
    assert "not professional audit or tax advice" in out


def test_non_interactive_start_prints_help_instead_of_prompting(capsys):
    """A piped `apg` must not open a prompt loop against a pipe and hang."""
    code = start(Session(quiet=True))
    out = capsys.readouterr().out
    assert code == 0
    assert "status" in out


def test_print_help_plain_lists_usage(capsys):
    print_help_plain(Session())
    assert "help [command]" in capsys.readouterr().out

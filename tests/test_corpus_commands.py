"""The `corpus` commands, against a small corpus built on disk.

No network anywhere: `built_corpus` writes two real standards into a temporary
directory, and the commands read them the same way they would read a genuine
download.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from apg import cli
from apg.commands import corpus as corpus_commands
from apg.dispatch import run
from apg.errors import ApgError
from apg.session import Session


@pytest.fixture
def session():
    return Session(quiet=True)


@pytest.fixture
def json_session():
    return Session(json_out=True)


def payload(capsys):
    return json.loads(capsys.readouterr().out)


# --- with nothing downloaded -------------------------------------------------


@pytest.mark.parametrize(
    ("tokens"),
    [
        ["corpus", "status"],
        ["corpus", "list"],
        ["corpus", "show", "2301"],
        ["corpus", "search", "risk"],
    ],
)
def test_every_reading_command_explains_that_there_is_no_corpus(tokens):
    """The expected state on a fresh clone: a next step, not a stack trace."""
    # debug=True makes the dispatcher re-raise instead of reporting, which is the
    # only way to inspect the error itself rather than its printed form.
    with pytest.raises(ApgError) as caught:
        run(Session(quiet=True, debug=True), tokens, mode="oneshot")
    assert "corpus download" in (caught.value.hint or "")


def test_the_missing_corpus_message_is_reported_not_crashed(session, capsys):
    code = run(session, ["corpus", "status"], mode="oneshot")
    assert code == 1
    assert "no corpus downloaded yet" in capsys.readouterr().out


# --- status ------------------------------------------------------------------


def test_status_reports_the_pin(built_corpus, json_session, capsys):
    corpus_commands.corpus_status(json_session)
    data = payload(capsys)
    assert data["version"] == "2026-08"
    assert data["standards"] == 2
    assert data["paragraphs"] > 0
    assert data["fingerprint"].startswith("sha256:")
    assert data["downloaded_utc"].endswith("Z")


# --- list --------------------------------------------------------------------


def test_list_shows_every_standard(built_corpus, json_session, capsys):
    corpus_commands.corpus_list(json_session)
    data = payload(capsys)
    assert {s["as_number"] for s in data["standards"]} == {"AS 2301", "AS 3110"}


def test_list_orders_by_series_then_number(built_corpus, json_session, capsys):
    corpus_commands.corpus_list(json_session)
    numbers = [s["as_number"] for s in payload(capsys)["standards"]]
    # Audit Procedures (2000s) is listed before Auditor Reporting (3000s).
    assert numbers.index("AS 2301") < numbers.index("AS 3110")


# --- show --------------------------------------------------------------------


@pytest.mark.parametrize("typed", ["2301", "AS2301", "as 2301", "AS 2301"])
def test_show_accepts_any_spelling_of_the_number(built_corpus, typed, capsys):
    """Including the unquoted two-word form, which is what people actually type."""
    session = Session(json_out=True)
    assert run(session, ["corpus", "show", *typed.split()], mode="oneshot") == 0
    assert payload(capsys)["as_number"] == "AS 2301"


def test_show_prints_headings_and_numbered_paragraphs(built_corpus, session, capsys):
    corpus_commands.corpus_show(session, "2301")
    out = capsys.readouterr().out
    assert "AS 2301" in out
    assert "Introduction" in out
    assert ".01" in out


def test_show_refuses_a_number_that_is_not_downloaded(built_corpus, session):
    with pytest.raises(ApgError, match="not in the downloaded corpus"):
        corpus_commands.corpus_show(session, "9999")


def test_show_refuses_something_that_is_not_a_number(built_corpus, session):
    with pytest.raises(ApgError, match="not an AS number"):
        corpus_commands.corpus_show(session, "banana")


# --- search ------------------------------------------------------------------


def test_search_finds_paragraphs_and_says_where(built_corpus, json_session, capsys):
    corpus_commands.corpus_search(json_session, "material misstatement")
    data = payload(capsys)
    assert data["matches"] > 0
    hit = data["hits"][0]
    assert hit["as_number"].startswith("AS ")
    assert hit["paragraph"].startswith(".")


def test_search_is_case_insensitive(built_corpus, json_session, capsys):
    corpus_commands.corpus_search(json_session, "MATERIAL MISSTATEMENT")
    assert payload(capsys)["matches"] > 0


def test_search_takes_an_unquoted_phrase(built_corpus, capsys):
    session = Session(json_out=True)
    run(session, ["corpus", "search", "material", "misstatement"], mode="oneshot")
    data = payload(capsys)
    assert data["term"] == "material misstatement"
    assert data["matches"] > 0


def test_search_with_no_matches_says_so_rather_than_failing(
    built_corpus, json_session, capsys
):
    corpus_commands.corpus_search(json_session, "zzzznotaword")
    assert payload(capsys)["matches"] == 0


def test_search_needs_something_to_look_for(built_corpus, session):
    with pytest.raises(ApgError, match="nothing to search for"):
        corpus_commands.corpus_search(session, "   ")


# --- the status strip and `status` ------------------------------------------


def test_status_command_picks_up_the_downloaded_corpus(built_corpus, capsys):
    """Nothing loads the corpus at startup, so `status` must find it on disk."""
    session = Session(json_out=True)
    run(session, ["status"], mode="oneshot")
    assert payload(capsys)["corpus_version"] == "2026-08"


def test_the_status_strip_shows_the_corpus_without_a_restart(built_corpus):
    from apg.repl import status_strip

    assert "corpus: 2026-08" in status_strip(Session())


def test_an_explicit_version_still_wins_over_what_is_on_disk(built_corpus):
    from apg.repl import status_strip

    session = Session(corpus_version="pinned-elsewhere")
    assert "corpus: pinned-elsewhere" in status_strip(session)


def test_the_strip_survives_an_unreadable_data_directory(monkeypatch):
    """A redraw happens on every keystroke; it must never be able to kill the shell."""
    from apg import paths
    from apg.repl import status_strip

    def boom():
        raise OSError("drive went away")

    monkeypatch.setattr(paths, "latest_corpus_version", boom)
    assert "corpus: not downloaded" in status_strip(Session())


# --- both surfaces -----------------------------------------------------------


def test_cli_and_direct_call_agree(built_corpus):
    """The one-shot CLI must not become a second implementation."""
    result = CliRunner().invoke(cli.app, ["corpus", "status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["version"] == "2026-08"


def test_download_is_never_run_by_help():
    """`--help` imports every command; none of them may touch the network."""
    result = CliRunner().invoke(cli.app, ["corpus", "download", "--help"])
    assert result.exit_code == 0
    assert "pcaobus.org" in result.output

"""Argument parsing and the mode-aware error boundary."""

from __future__ import annotations

import pytest

from apg.dispatch import ExitSession, coerce, parse_args, run, split
from apg.errors import ApgError
from apg.registry import Command, Param
from apg.session import Session


@pytest.fixture
def session():
    # quiet keeps test output clean and suppresses the mascot deterministically.
    return Session(quiet=True)


def make(*params: Param) -> Command:
    return Command("demo", lambda session, *args: args, "demo", params)


def test_split_respects_quotes():
    assert split('corpus show "AS 2301"') == ["corpus", "show", "AS 2301"]


def test_split_survives_unbalanced_quotes():
    """A stray apostrophe must degrade, not raise."""
    assert split("what's this") == ["what's", "this"]


def test_missing_required_argument_names_it():
    cmd = make(Param("as_number", "h"))
    with pytest.raises(ApgError) as exc:
        parse_args(cmd, [])
    assert "as_number" in str(exc.value)
    assert exc.value.hint == "usage: demo <as_number>"


def test_optional_argument_may_be_omitted():
    cmd = make(Param("fmt", "h", required=False))
    assert parse_args(cmd, []) == []


def test_a_rest_parameter_swallows_the_whole_line():
    """`corpus show AS 2301` is one argument, not a command with a surplus word."""
    cmd = make(Param("as_number", "h", rest=True))
    assert parse_args(cmd, ["AS", "2301"]) == ["AS 2301"]


def test_a_rest_parameter_leaves_earlier_arguments_alone():
    cmd = make(Param("model", "h"), Param("question", "h", rest=True))
    assert parse_args(cmd, ["qwen", "what", "does", "AS", "2301", "require"]) == [
        "qwen",
        "what does AS 2301 require",
    ]


def test_a_rest_parameter_accepts_a_single_word():
    cmd = make(Param("term", "h", rest=True))
    assert parse_args(cmd, ["risk"]) == ["risk"]


def test_a_rest_parameter_is_still_required_when_absent():
    cmd = make(Param("term", "h", rest=True))
    with pytest.raises(ApgError, match="term"):
        parse_args(cmd, [])


def test_quoting_a_rest_argument_changes_nothing():
    """Both spellings must reach the command identically."""
    cmd = make(Param("as_number", "h", rest=True))
    assert parse_args(cmd, split('demo "AS 2301"')[1:]) == parse_args(
        cmd, split("demo AS 2301")[1:]
    )


def test_surplus_arguments_are_refused():
    cmd = make(Param("a", "h"))
    with pytest.raises(ApgError, match="does not take"):
        parse_args(cmd, ["one", "two"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [("yes", True), ("no", False), ("1", True), ("off", False), ("TRUE", True)],
)
def test_bool_coercion(text, expected):
    assert coerce(text, bool, "flag") is expected


def test_bad_int_explains_itself():
    with pytest.raises(ApgError, match="should be a int"):
        coerce("many", int, "count")


def test_unknown_command_suggests_a_correction(session, capsys):
    code = run(session, ["statuss"], mode="oneshot")
    assert code == 1
    assert "did you mean `status`?" in capsys.readouterr().out


def test_empty_input_is_a_no_op(session):
    assert run(session, [], mode="repl") == 0


def test_errors_return_one_in_both_modes(session):
    assert run(session, ["nope"], mode="oneshot") == 1
    assert run(session, ["nope"], mode="repl") == 1


def test_debug_reraises_instead_of_reporting():
    session = Session(quiet=True, debug=True)
    with pytest.raises(ApgError):
        run(session, ["nope"], mode="oneshot")


def test_exit_unwinds_rather_than_being_swallowed(session):
    """`exit` must escape run() so the REPL loop can end."""
    with pytest.raises(ExitSession):
        run(session, ["exit"], mode="repl")


def test_ctrl_c_cancels_the_command_but_not_the_session(session, monkeypatch):
    """In the shell a cancelled command returns 0; one-shot uses the usual 130."""
    from apg import registry

    def boom(session):
        raise KeyboardInterrupt

    fake = dict(registry.REGISTRY)
    fake["slow"] = Command("slow", boom, "pretend this takes a while")
    monkeypatch.setattr("apg.registry.REGISTRY", fake)

    assert run(session, ["slow"], mode="repl") == 0
    assert run(session, ["slow"], mode="oneshot") == 130

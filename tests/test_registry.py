"""The registry itself, and the guard that keeps it the single source of truth."""

from __future__ import annotations

import pytest

from apg import cli
from apg.registry import REGISTRY, Command, Param, all_commands, resolve


def test_the_expected_commands_are_registered():
    """Deliberately an exact set.

    A command appearing here that nobody meant to ship — or one quietly
    disappearing — is worth failing over, so this list is updated by hand at each
    phase boundary rather than derived from the registry it is checking.
    """
    assert set(REGISTRY) == {
        "help",
        "status",
        "exit",
        "corpus download",
        "corpus status",
        "corpus list",
        "corpus show",
        "corpus search",
        "data estimate",
        "data verify",
        "data prepare",
        "data generate",
        "data validate",
        "data finalize",
        "data stats",
        "data sample",
    }


def test_usage_marks_required_and_optional_differently():
    cmd = Command(
        name="corpus show",
        fn=lambda session, a, b=None: None,
        help="x",
        params=(Param("as_number", "h"), Param("fmt", "h", required=False)),
    )
    assert cmd.usage() == "corpus show <as_number> [fmt]"
    assert cmd.group == "corpus"


def test_usage_marks_a_rest_parameter_with_an_ellipsis():
    """`<term...>` is the only signal that quoting a phrase is unnecessary."""
    cmd = Command(
        name="corpus search",
        fn=lambda session, term: None,
        help="x",
        params=(Param("term", "h", rest=True),),
    )
    assert cmd.usage() == "corpus search <term...>"


def test_a_rest_parameter_must_come_last():
    """Anything declared behind one could never be filled, so refuse it outright."""
    from apg.registry import command

    with pytest.raises(ValueError, match="must be the last parameter"):
        command(
            "bogus",
            "x",
            params=(Param("a", "h", rest=True), Param("b", "h")),
        )(lambda session, a, b: None)


def test_single_word_command_has_no_group():
    assert REGISTRY["status"].group is None


def test_resolve_prefers_the_longest_match(monkeypatch):
    """A two-word command must win over a one-word command sharing its first word."""
    fake = dict(REGISTRY)
    fake["corpus"] = Command("corpus", lambda s: None, "group")
    fake["corpus show"] = Command("corpus show", lambda s, n: None, "leaf")
    monkeypatch.setattr("apg.registry.REGISTRY", fake)

    cmd, rest = resolve(["corpus", "show", "AS", "2301"])
    assert cmd.name == "corpus show"
    assert rest == ["AS", "2301"]


def test_resolve_returns_none_for_unknown():
    assert resolve(["nonsense"]) is None


def test_duplicate_registration_is_refused():
    from apg.registry import command

    with pytest.raises(ValueError, match="already registered"):
        command("status", "duplicate")(lambda session: None)


def test_cli_and_registry_expose_exactly_the_same_commands():
    """The anti-drift guard.

    If a later phase ever adds a command straight to the Typer app instead of the
    registry — the "parallel implementations" failure this project is built to
    avoid — this test fails.
    """
    import typer.main

    group = typer.main.get_command(cli.app)
    cli_names = set()
    for name, sub in group.commands.items():
        children = getattr(sub, "commands", None)
        if children:
            cli_names.update(f"{name} {child}" for child in children)
        else:
            cli_names.add(name)

    assert cli_names == {cmd.name for cmd in all_commands()}

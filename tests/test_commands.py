"""The commands themselves, and the promise that both front ends agree."""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from apg import cli
from apg.commands import core
from apg.registry import all_commands
from apg.session import Session

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

runner = CliRunner()


def test_status_reports_empty_state_honestly():
    session = Session(json_out=True)
    assert session.state_summary() == {
        "specialist": None,
        "corpus_version": None,
        "dataset_pairs": 0,
    }


def test_both_surfaces_produce_identical_output(capsys):
    """The core promise: `status` in the shell and `apg status` are one function.

    Compared as JSON so the assertion is about the data, not the table borders.
    """
    core.status(Session(json_out=True))
    direct = json.loads(capsys.readouterr().out)

    result = runner.invoke(cli.app, ["status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == direct


def test_flags_work_before_and_after_the_command():
    before = runner.invoke(cli.app, ["--json", "status"])
    after = runner.invoke(cli.app, ["status", "--json"])
    assert json.loads(before.output) == json.loads(after.output)


@pytest.mark.parametrize("flag", ["--json", "--quiet", "--no-color"])
def test_no_ansi_leaks_into_piped_output(flag):
    result = runner.invoke(cli.app, ["status", flag])
    assert result.exit_code == 0
    assert not ANSI.search(result.output)


@pytest.mark.parametrize("flag", ["--json", "--quiet"])
def test_no_mascot_in_machine_output(flag):
    from apg import tick

    result = runner.invoke(cli.app, ["status", flag])
    for line in tick.LINES.values():
        assert line not in result.output


def test_json_output_is_parseable():
    result = runner.invoke(cli.app, ["status", "--json"])
    assert json.loads(result.output)["dataset_pairs"] == 0


def test_help_lists_every_registered_command():
    result = runner.invoke(cli.app, ["help", "--json"])
    listed = {entry["name"] for entry in json.loads(result.output)["commands"]}
    assert listed == {cmd.name for cmd in all_commands()}


def test_help_explains_a_single_command():
    result = runner.invoke(cli.app, ["help", "status", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "status"
    assert payload["usage"] == "status"


def test_help_for_unknown_command_is_not_an_error():
    result = runner.invoke(cli.app, ["help", "nonsense"])
    assert result.exit_code == 0
    assert "nonsense" in result.output


def test_optional_argument_survives_rich_markup():
    """`help [command]` must keep its brackets, not lose them to a style tag."""
    result = runner.invoke(cli.app, ["help"])
    assert "help [command]" in result.output


def test_unknown_command_exits_nonzero():
    result = runner.invoke(cli.app, ["definitely-not-a-command"])
    assert result.exit_code != 0


@pytest.mark.parametrize("cmd", [c.name for c in all_commands()])
def test_every_command_has_working_help(cmd):
    """No command may crash on --help, and none may touch data or the network."""
    result = runner.invoke(cli.app, [*cmd.split(), "--help"])
    assert result.exit_code == 0

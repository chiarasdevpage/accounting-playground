"""The three commands that exist in Phase 1: `help`, `status`, `exit`.

Every one of these is a plain function whose first argument is the Session. None
of them import Typer or prompt_toolkit, which is the point — they are callable
from either front end, and from a test, with nothing set up.
"""

from __future__ import annotations

from apg.console import build_table, emit, say
from apg.dispatch import ExitSession
from apg.registry import Param, all_commands, command
from apg.session import Session


@command(
    "help",
    "List every command, or explain one of them.",
    params=(Param("command", "the command to explain", required=False),),
)
def help_(session: Session, command_name: str | None = None) -> None:
    if command_name:
        matches = [c for c in all_commands() if c.name == command_name]
        if not matches:
            # Not an error worth a dizzy Tick — just point at the list.
            say(session, f"no command called {command_name!r}. try `help`.")
            return
        cmd = matches[0]
        emit(
            session,
            {"command": cmd.name, "help": cmd.help, "usage": cmd.usage()},
            build_table(
                cmd.name,
                ["usage", "what it does"],
                [[cmd.usage(), cmd.help]],
                keep_whole=["usage"],
            ),
        )
        return

    commands = all_commands()
    emit(
        session,
        {"commands": [{"name": c.name, "help": c.help} for c in commands]},
        build_table(
            "commands",
            ["command", "what it does"],
            [[c.usage(), c.help] for c in commands],
            keep_whole=["command"],
        ),
    )


@command("status", "Show what this build currently has loaded.")
def status(session: Session) -> None:
    state = session.state_summary()

    # Phase 1 has nothing loaded, and says so plainly rather than pretending.
    rows = [
        ["active specialist", state["specialist"] or "none"],
        ["corpus version", state["corpus_version"] or "not downloaded"],
        ["dataset pairs", state["dataset_pairs"] or "none generated"],
    ]
    emit(session, state, build_table("status", ["item", "value"], rows))

    if not any([state["specialist"], state["corpus_version"], state["dataset_pairs"]]):
        say(
            session,
            "nothing loaded yet — Phase 1 is the shell only.",
            style="dim",
        )


@command("exit", "Leave the shell.")
def exit_(session: Session) -> None:
    say(session, "bye.", style="dim")
    raise ExitSession

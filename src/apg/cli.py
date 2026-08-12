"""The one-shot CLI — `apg status`, `apg help`, and so on.

Plain-English picture: this file builds the terminal interface, but it does not
define a single command. It walks the registry and generates one thin Typer
handler per entry, each of which hands its words straight back to the shared
dispatcher. Nothing here knows what `status` does.

That is the whole point. A command added in a later phase appears in the CLI, in
the shell, in `help`, and in tab completion, having been written once.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.markup import escape

import apg.commands  # noqa: F401 - importing the package registers every command
from apg import __version__
from apg.dispatch import ExitSession, run
from apg.registry import Command, all_commands
from apg.session import Session

app = typer.Typer(
    name="apg",
    help=(
        "Accounting Playground — a testing ground for accounting assistants. "
        "Research/education artifact, not professional audit or tax advice."
    ),
    add_completion=False,
    # Handled in the callback so that a bare `apg` opens the interactive shell
    # rather than dumping help. Typer's own no_args_is_help would bypass it.
    no_args_is_help=False,
)

# Sub-apps for multi-word commands ("corpus show"), created on demand.
_groups: dict[str, typer.Typer] = {}

Args = Annotated[list[str] | None, typer.Argument(help="command arguments")]

# The global flags, declared once and accepted in both positions: before the
# command (`apg --json status`) and after it (`apg status --json`).
JsonFlag = Annotated[bool, typer.Option("--json", help="machine-readable output")]
QuietFlag = Annotated[bool, typer.Option("--quiet", help="suppress chatter and colour")]
ColorFlag = Annotated[bool, typer.Option("--no-color", help="strip ANSI styling")]
DebugFlag = Annotated[bool, typer.Option("--debug", help="show full tracebacks")]


def _apply_flags(
    session: Session,
    json_out: bool,
    quiet: bool,
    no_color: bool,
    debug: bool,
) -> None:
    """Let flags be given after the command too, so `apg status --json` works.

    Only ever turns a flag on: the root callback may already have set it from
    `apg --json status`, and that must not be undone here.
    """
    session.json_out = session.json_out or json_out
    session.quiet = session.quiet or quiet
    session.no_color = session.no_color or no_color
    session.debug = session.debug or debug


def _make_handler(cmd: Command):
    """Build the Typer handler for one registered command."""

    def handler(
        ctx: typer.Context,
        args: Args = None,
        json_out: JsonFlag = False,
        quiet: QuietFlag = False,
        no_color: ColorFlag = False,
        debug: DebugFlag = False,
    ) -> None:
        session = ctx.obj if isinstance(ctx.obj, Session) else Session()
        _apply_flags(session, json_out, quiet, no_color, debug)
        tokens = cmd.name.split() + list(args or [])
        try:
            code = run(session, tokens, mode="oneshot")
        except ExitSession:
            # `apg exit` outside the shell is a no-op that succeeds.
            code = 0
        raise typer.Exit(code)

    handler.__name__ = cmd.name.replace(" ", "_")
    # Typer renders docstrings through Rich, which would eat the square brackets
    # around optional arguments as a style tag.
    handler.__doc__ = f"{cmd.help}  (usage: {escape(cmd.usage())})"
    return handler


def _register_all() -> None:
    """Mirror every registry entry into the Typer app.

    Multi-word names become Typer sub-groups, so `corpus show` is reachable as
    `apg corpus show` without the dispatcher needing to know about groups.
    """
    for cmd in all_commands():
        handler = _make_handler(cmd)
        group = cmd.group
        if group is None:
            app.command(cmd.name)(handler)
            continue
        if group not in _groups:
            _groups[group] = typer.Typer(help=f"{group} commands", no_args_is_help=True)
            app.add_typer(_groups[group], name=group)
        _groups[group].command(cmd.name.split(" ", 1)[1])(handler)


_register_all()


def _version(value: bool) -> None:
    if value:
        typer.echo(f"apg {__version__}")
        raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_out: JsonFlag = False,
    quiet: QuietFlag = False,
    no_color: ColorFlag = False,
    debug: DebugFlag = False,
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True)
    ] = False,
) -> None:
    session = Session(json_out=json_out, quiet=quiet, no_color=no_color, debug=debug)
    ctx.obj = session

    if ctx.invoked_subcommand is None:
        from apg.repl import start

        raise typer.Exit(start(session))


if __name__ == "__main__":  # pragma: no cover
    app()

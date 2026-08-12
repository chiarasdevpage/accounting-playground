"""The interactive shell — `apg` with no arguments.

Plain-English picture: a banner, Tick, a status strip pinned to the bottom of the
window, and an `apg>` prompt with command history and tab completion. Everything
you type is handed straight to the shared dispatcher, so the shell contains no
command logic of its own — only the loop and the decoration around it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory

from apg import tick
from apg.console import FOOTER, RULE, SEP
from apg.dispatch import ExitSession, run, split
from apg.registry import REGISTRY, all_commands
from apg.session import Session

HISTORY_PATH = Path.home() / ".apg_history"

PROMPT = "apg> "


class RegistryCompleter(Completer):
    """Tab completion driven entirely by the registry.

    Because it reads REGISTRY rather than a hand-maintained list, every command
    added in a later phase becomes completable with no change here.
    """

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        typed = document.text_before_cursor.lstrip()
        for name in sorted(REGISTRY):
            if name.startswith(typed) and name != typed:
                yield Completion(name, start_position=-len(typed))


def status_strip(session: Session) -> str:
    """The one-line summary pinned under the prompt.

    Reads `Session.state_summary`, the same source `status` uses, so the strip and
    the command can never disagree about what is loaded.
    """
    state = session.state_summary()
    parts = [
        f"specialist: {state['specialist'] or 'none'}",
        f"corpus: {state['corpus_version'] or 'not downloaded'}",
        f"pairs: {state['dataset_pairs'] or 0}",
    ]
    return f" {f'  {SEP}  '.join(parts)} "


def banner(session: Session) -> None:
    """Tick, the wordmark, and the standing caveat."""
    console = session.console
    if session.mascot_enabled:
        console.print(tick.render("idle"), style="cyan")
    console.print("accounting playground", style="bold")
    console.print("audit standards specialist bench", style="dim")
    console.print(RULE * 44, style="dim")
    console.print(FOOTER, style="dim")
    console.print(f"type {'help'!r} to see what works, {'exit'!r} to leave.\n")


def repl(session: Session) -> int:
    """Run the interactive loop. Returns the process exit code."""
    banner(session)

    prompt_session: PromptSession[str] = PromptSession(
        history=FileHistory(str(HISTORY_PATH)),
        completer=RegistryCompleter(),
        complete_while_typing=False,
        bottom_toolbar=lambda: status_strip(session),
    )

    while True:
        try:
            line = prompt_session.prompt(PROMPT)
        except KeyboardInterrupt:
            # Ctrl-C clears the current line and returns the prompt. It does not
            # leave the session — that is what Ctrl-D and `exit` are for.
            continue
        except EOFError:
            # Ctrl-D. Leave cleanly and quietly.
            session.console.print("bye.", style="dim")
            return 0

        try:
            run(session, split(line), mode="repl")
        except ExitSession:
            return 0


def print_help_plain(session: Session) -> None:
    """Fallback for a non-interactive `apg`: list commands instead of prompting.

    Starting a prompt loop against a pipe would hang, so piped invocations get
    the command list and exit.
    """
    console = session.console
    console.print("accounting playground", style="bold")
    for cmd in all_commands():
        console.print(f"  {cmd.usage():<24} {cmd.help}")
    console.print(f"\n{FOOTER}", style="dim")


def start(session: Session) -> int:
    """Enter the shell if there is a human at the keyboard; otherwise print help."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print_help_plain(session)
        return 0
    return repl(session)


__all__ = ["banner", "repl", "start", "status_strip"]

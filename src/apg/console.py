"""Output plumbing shared by every `apg` command.

Plain-English picture: this module is the app's mouth. Commands compute plain
Python dictionaries and lists; this decides whether a human sees a coloured Rich
table or a machine sees JSON. Keeping that decision in one place is what lets
`--json` and `--quiet` work everywhere without each command reimplementing them.

Nothing here does accounting. It formats what the rest of the app computed.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from rich.table import Table

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, types only
    from apg.session import Session


def _force_utf8() -> None:
    """Make stdout/stderr UTF-8 where the platform allows it.

    Windows consoles still default to cp1252, which cannot encode the box-drawing
    glyphs Tick is made of. Reconfiguring is the fix; `supports_unicode` below is
    the fallback for cases where it isn't possible (a redirected pipe under an
    exotic codepage, say).
    """
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


def supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "─│—·".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


_force_utf8()
UNICODE = supports_unicode()

# Printed by the REPL banner and by anything that reports model output. The
# caveat is a project ground rule, not decoration — do not paraphrase it away.
FOOTER = "research/education artifact — not professional audit or tax advice"
if not UNICODE:
    FOOTER = FOOTER.replace("—", "-")

RULE = "─" if UNICODE else "-"
SEP = "·" if UNICODE else "-"


def dash(text: str) -> str:
    """Em dashes are decorative; downgrade them rather than crash."""
    return text if UNICODE else text.replace("—", "-")


def fmt(value: Any, sig: int = 4) -> str:
    """Format a number to `sig` significant figures; pass everything else through."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value != value:  # NaN
            return "nan"
        if value == 0:
            return "0"
        return f"{value:#.{sig}g}"
    return str(value)


def build_table(
    title: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    numeric: Sequence[str] = (),
    keep_whole: Sequence[str] = (),
) -> Table:
    """A Rich table with numbers right-aligned and values at 4 significant figures.

    `numeric` names the columns that should be right-aligned; everything else is
    left-aligned. `keep_whole` names columns that must never be truncated with an
    ellipsis — identifiers such as AS numbers stay readable, prose wraps instead.
    """
    table = Table(title=dash(title), title_justify="left", header_style="bold")
    for name in columns:
        table.add_column(
            dash(name),
            justify="right" if name in numeric else "left",
            no_wrap=name in numeric,
            overflow="fold" if name in keep_whole else "ellipsis",
        )
    for row in rows:
        table.add_row(*[dash(fmt(cell)) for cell in row])
    return table


def emit(
    session: Session,
    payload: dict[str, Any],
    table: Table | None = None,
    footer: bool = False,
) -> None:
    """The single output call.

    `payload` is the machine-readable truth; `table` is the human rendering of the
    same numbers. Under --json only the payload is printed, so the two must never
    disagree.
    """
    if session.json_out:
        json.dump(payload, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return

    console = session.console
    if table is not None:
        console.print(table)
    if footer:
        console.print(FOOTER, style="dim")


@contextlib.contextmanager
def progress(session: Session, total: int, description: str) -> Iterator[Any]:
    """A progress bar for work that takes long enough to look frozen without one.

    Yields an object with `advance()`. Under --json or --quiet it yields a silent
    stand-in, so a command calls `advance()` unconditionally and never has to ask
    whether anything is being displayed — the same reason `emit` and `say` exist.
    """
    if session.json_out or session.quiet or not sys.stdout.isatty():
        yield _SilentProgress()
        return

    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=session.console,
        transient=True,
    ) as bar:
        task = bar.add_task(dash(description), total=total)
        yield _RichProgress(bar, task)


class _SilentProgress:
    def advance(self, step: int = 1, description: str | None = None) -> None:
        return


class _RichProgress:
    def __init__(self, bar: Any, task: Any) -> None:
        self._bar = bar
        self._task = task

    def advance(self, step: int = 1, description: str | None = None) -> None:
        if description is not None:
            self._bar.update(self._task, description=dash(description))
        self._bar.advance(self._task, step)


def say(session: Session, message: str, style: str = "") -> None:
    """Human-only chatter. Silent under --json and --quiet."""
    if session.json_out or session.quiet:
        return
    session.console.print(message, style=style)


def show_mascot(session: Session, state: str, style: str = "cyan") -> None:
    """Print Tick in `state`, but only when a mascot is welcome.

    Every mascot call site goes through here so the suppression policy is applied
    in exactly one place and can never drift between commands.
    """
    if not session.mascot_enabled:
        return
    from apg import tick

    session.console.print(tick.render(state), style=style)

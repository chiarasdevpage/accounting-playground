"""Turning a typed line into a called function — once, for both front ends.

Plain-English picture: the shell and the CLI both hand this module a list of
words. It finds the matching command, checks you supplied the right arguments,
converts them to the right types, calls the function, and decides what to do if
anything goes wrong.

The last part is the only place the two surfaces genuinely differ, and it is one
parameter: a bad command from your terminal should end the process with a failure
code, while a bad command at the `apg>` prompt should print the problem and give
you the prompt back. Killing an interactive session over a typo would be rude
now, and actively expensive later, when exiting means discarding a multi-gigabyte
model you waited a minute to load.
"""

from __future__ import annotations

import difflib
import shlex
from typing import Any, Literal

from apg.errors import ApgError, report
from apg.registry import REGISTRY, Command, resolve
from apg.session import Session

Mode = Literal["repl", "oneshot"]


class ExitSession(Exception):  # noqa: N818 - control flow, not a failure
    """Raised by `exit` to unwind the REPL loop. Never an error."""


def split(line: str) -> list[str]:
    """Split a typed line into words, respecting quotes.

    Falls back to a plain split when quoting is unbalanced, so a stray apostrophe
    produces an "unknown command" message rather than a crash.
    """
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()


def coerce(value: str, target: type, param_name: str) -> Any:
    """Convert one typed-in string to the type the command declared."""
    if target is str:
        return value
    if target is bool:
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "on"}:
            return True
        if lowered in {"false", "no", "n", "0", "off"}:
            return False
        raise ApgError(
            f"{param_name} should be yes or no, not {value!r}",
            hint="try: yes, no, true, false, 1, 0",
        )
    try:
        return target(value)
    except (TypeError, ValueError) as exc:
        raise ApgError(
            f"{param_name} should be a {target.__name__}, not {value!r}"
        ) from exc


def parse_args(cmd: Command, tokens: list[str]) -> list[Any]:
    """Check arity and convert each argument. Raises ApgError with the usage line."""
    # A trailing rest-parameter collapses everything still unconsumed into one
    # argument, so `corpus show AS 2301` and `corpus show "AS 2301"` are the same
    # call and neither needs the user to think about quoting.
    if cmd.params and cmd.params[-1].rest and len(tokens) > len(cmd.params):
        head = tokens[: len(cmd.params) - 1]
        tokens = [*head, " ".join(tokens[len(cmd.params) - 1 :])]

    required = [p for p in cmd.params if p.required]
    if len(tokens) < len(required):
        missing = [p.name for p in cmd.params[len(tokens) :] if p.required]
        raise ApgError(
            f"{cmd.name} needs {', '.join(missing)}",
            hint=f"usage: {cmd.usage()}",
        )
    if len(tokens) > len(cmd.params):
        extra = " ".join(tokens[len(cmd.params) :])
        raise ApgError(
            f"{cmd.name} does not take {extra!r}",
            hint=f"usage: {cmd.usage()}",
        )
    return [
        coerce(token, param.type, param.name)
        for token, param in zip(tokens, cmd.params, strict=False)
    ]


def _unknown(tokens: list[str]) -> ApgError:
    """An 'unknown command' error, with a spelling suggestion when there is one."""
    typed = " ".join(tokens)
    close = difflib.get_close_matches(typed, list(REGISTRY), n=1, cutoff=0.6)
    hint = f"did you mean `{close[0]}`?" if close else "run `help` to see every command"
    return ApgError(f"unknown command: {typed}", hint=hint)


def run(session: Session, tokens: list[str], mode: Mode) -> int:
    """Dispatch `tokens` and return an exit code (0 success, 1 failure).

    `ExitSession` is re-raised rather than handled — it is how `exit` unwinds the
    REPL, not a failure. Everything else is reported here.
    """
    if not tokens:
        return 0

    try:
        match = resolve(tokens)
        if match is None:
            raise _unknown(tokens)
        cmd, rest = match
        args = parse_args(cmd, rest)
        cmd.fn(session, *args)
        return 0
    except ExitSession:
        raise
    except KeyboardInterrupt:
        # Ctrl-C during a running command cancels that command only. In the REPL
        # you get the prompt back; one-shot uses the conventional 130.
        if session.json_out:
            from apg.console import emit

            emit(
                session,
                {"error": {"type": "KeyboardInterrupt", "message": "cancelled"}},
            )
        else:
            session.console.print("cancelled", style="dim")
        return 0 if mode == "repl" else 130
    except Exception as exc:  # noqa: BLE001 - deliberate top-level handler
        if session.debug:
            raise
        report(session, exc)
        return 1

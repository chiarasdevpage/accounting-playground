"""Plain-English error handling.

Plain-English picture: when something breaks, you want one sentence telling you
what to do next — not forty lines of Python traceback. `ApgError` carries both
the explanation and the suggested next step; `report` prints them with a dizzy
Tick on top, and the traceback appears only when you ask with --debug.

Note what is deliberately *absent*: this module does not decide whether to exit.
The same failure should end the process from a one-shot `apg status` but return
you to the prompt inside the interactive shell, so that decision lives in
`dispatch.run`, which knows which surface it is serving.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apg.console import show_mascot

if TYPE_CHECKING:  # pragma: no cover - types only
    from apg.session import Session


class ApgError(Exception):
    """An error we anticipated and can explain in one sentence.

    Raise this (rather than a bare Exception) whenever the app knows both what
    went wrong and what the user should do about it. `hint` is printed as the
    suggested next step.
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


# Exceptions from elsewhere that we can translate without showing a traceback.
# Maps exception class name -> suggested next step.
_KNOWN_HINTS = {
    "FileNotFoundError": "run `status` to see what this build actually has",
    "ModuleNotFoundError": "run `uv sync` to install the project's dependencies",
    "PermissionError": "another program may be holding that file open",
    # The corpus download is the first thing here that talks to the network, and
    # httpx's own messages ("ConnectError: [Errno 11001]") explain nothing to
    # someone who just wants to know whether it was them or the website.
    "ConnectError": "check your internet connection; pcaobus.org may also be down",
    "ConnectTimeout": "the connection timed out - try `corpus download` again",
    "ReadTimeout": "pcaobus.org stopped responding - try `corpus download` again",
    "HTTPStatusError": "pcaobus.org refused that request; it may have moved the page",
}


def report(session: Session, exc: BaseException) -> None:
    """Print the apology, the one-line cause, and the suggested next step."""
    console = session.console
    hint = getattr(exc, "hint", None) or _KNOWN_HINTS.get(type(exc).__name__)

    if session.json_out:
        from apg.console import emit

        emit(
            session,
            {"error": {"type": type(exc).__name__, "message": str(exc), "hint": hint}},
        )
        return

    # Tick apologises first, then gets out of the way. Whimsy never replaces the
    # error text.
    show_mascot(session, "dizzy", style="yellow")

    if isinstance(exc, ApgError):
        # We anticipated this one: the message IS the explanation, and its
        # traceback points at our own raise statement, so don't advertise it.
        console.print(str(exc), style="bold red")
    else:
        console.print(f"{type(exc).__name__}: {exc}", style="bold red")

    if hint:
        console.print(f"try: {hint}", style="dim")
    if not session.debug and not isinstance(exc, ApgError):
        console.print("re-run with --debug for the full traceback", style="dim")

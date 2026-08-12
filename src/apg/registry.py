"""The command registry — the one place a command is defined.

Plain-English picture: every feature of this app is a command, and every command
is registered here exactly once. The interactive shell and the one-shot CLI both
read this same table, so `status` typed at the `apg>` prompt and `apg status`
typed at your terminal run literally the same function. There is never a second
implementation to keep in sync.

That rule is worth the small amount of machinery below. The sibling project
BipGPT attached its commands directly to its CLI framework, which baked framework
types into every function signature; nothing but that framework could call them,
so adding an interactive shell later would have meant writing every command
twice. Commands here are plain functions that know nothing about Typer or
prompt_toolkit.

Adding a command, in full:

    @command("corpus show", "Print one auditing standard.",
             params=(Param("as_number", "e.g. AS 2301"),))
    def corpus_show(session: Session, as_number: str) -> None:
        ...

It is now dispatchable from both surfaces, tab-completable, and listed in `help`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Param:
    """One argument a command accepts.

    Declared rather than inferred from the Python signature, because both front
    ends must parse arguments identically and one shared spec guarantees that by
    construction.
    """

    name: str
    help: str
    required: bool = True
    type: type = str


@dataclass(frozen=True)
class Command:
    """A registered command.

    `name` may contain spaces ("corpus show"). Group commands are stored under
    their full name and resolved by longest-prefix match, so command groups need
    no special handling in the dispatcher.
    """

    name: str
    fn: Callable[..., object]
    help: str
    params: tuple[Param, ...] = field(default_factory=tuple)

    @property
    def group(self) -> str | None:
        """The first word, for multi-word commands like "corpus show"."""
        head, _, rest = self.name.partition(" ")
        return head if rest else None

    def usage(self) -> str:
        """A one-line usage string: `corpus show <as_number>`."""
        parts = [self.name]
        for param in self.params:
            parts.append(f"<{param.name}>" if param.required else f"[{param.name}]")
        return " ".join(parts)


REGISTRY: dict[str, Command] = {}


def command(
    name: str,
    help: str,
    params: tuple[Param, ...] = (),
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Register a function as a command.

    The decorated function keeps its plain signature — `(session, *params)` — and
    is returned unchanged, so it stays directly importable and unit-testable
    without going through either front end.
    """

    def decorator(fn: Callable[..., object]) -> Callable[..., object]:
        if name in REGISTRY:
            raise ValueError(f"command {name!r} is already registered")
        REGISTRY[name] = Command(name=name, fn=fn, help=help, params=tuple(params))
        return fn

    return decorator


def resolve(tokens: list[str]) -> tuple[Command, list[str]] | None:
    """Match the longest registered command name at the front of `tokens`.

    Returns the command and its remaining arguments, or None if nothing matches.
    Longest-first is what lets "corpus show" win over a hypothetical "corpus".
    """
    for size in range(min(len(tokens), 3), 0, -1):
        candidate = " ".join(tokens[:size])
        if candidate in REGISTRY:
            return REGISTRY[candidate], tokens[size:]
    return None


def all_commands() -> list[Command]:
    """Every command, sorted by name — the order `help` and completion use."""
    return sorted(REGISTRY.values(), key=lambda cmd: cmd.name)

"""Importing this package registers every command.

Each submodule's `@command` decorators fire on import, so this file is the single
place that decides which command modules exist. Later phases add a line here —
`from apg.commands import corpus` — and nothing else needs to change.
"""

from __future__ import annotations

from apg.commands import core  # noqa: F401 - imported for its registration side effect

__all__ = ["core"]

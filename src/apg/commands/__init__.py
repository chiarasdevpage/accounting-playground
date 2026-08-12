"""Importing this package registers every command.

Each submodule's `@command` decorators fire on import, so this file is the single
place that decides which command modules exist. Later phases add a line here —
`from apg.commands import corpus` — and nothing else needs to change.
"""

from __future__ import annotations

from apg.commands import (  # noqa: F401 - imported for their registration side effect
    core,
    corpus,
)

__all__ = ["core", "corpus"]

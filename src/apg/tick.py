"""Tick, the mascot.

Plain-English picture: Tick is a small ASCII ledger critter that reacts to what
the app is doing — pleased when the numbers tie out, dizzy when something breaks,
sleepy during long downloads. The name is auditor jargon: to "tick and tie" is to
check work against its source, and the marks down Tick's belly are those ticks.

Tick is decoration and nothing else. He never appears under --json, --quiet,
APG_NO_MASCOT=1, or when output is piped, and no command's behaviour or exit code
ever depends on him. Whimsy never blocks the work.
"""

from __future__ import annotations

# One body, three swappable slots. Every substituted string is padded to a fixed
# width below so the frame never shifts between states.
_BODY = """\
  .--------------.
  |              |
  |   {eyes}   |
  |     {mouth}     |
  |   {belly}    |
  '--.________.--'
       |    |
      _/    \\_
"""

# eyes: 8 chars | mouth: 4 chars | belly: 7 chars. Keep these widths.
FACES: dict[str, dict[str, str]] = {
    "idle":   {"eyes": "O      O", "mouth": "\\__/", "belly": ". . . ."},
    "happy":  {"eyes": "^      ^", "mouth": "\\__/", "belly": "v v v v"},
    "dizzy":  {"eyes": "@      @", "mouth": " ~~ ", "belly": "? ? ? ?"},
    "sleepy": {"eyes": "-      -", "mouth": " .. ", "belly": ". . . ."},
}

# One-liners Tick says alongside each face.
LINES: dict[str, str] = {
    "idle": "tick.",
    "happy": "tick! ties out.",
    "dizzy": "tick... that doesn't reconcile.",
    "sleepy": "tick... zzz. this may take a while.",
}


def render(state: str = "idle", say: bool = True) -> str:
    """Return Tick's face for `state`, with his line underneath.

    Unknown states fall back to `idle` rather than raising — a mascot must never
    be the reason a command fails.
    """
    face = FACES.get(state, FACES["idle"])
    art = _BODY.format(**face)
    if say:
        art += f"\n   {LINES.get(state, LINES['idle'])}"
    return art

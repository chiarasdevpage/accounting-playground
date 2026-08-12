"""Tick must never be the reason something fails."""

from __future__ import annotations

import pytest

from apg import tick
from apg.session import Session


@pytest.mark.parametrize("state", sorted(tick.FACES))
def test_every_state_renders(state):
    art = tick.render(state)
    assert tick.LINES[state] in art


def test_unknown_state_falls_back_to_idle():
    assert tick.render("no-such-state") == tick.render("idle")


def test_every_face_has_a_line():
    assert set(tick.FACES) == set(tick.LINES)


@pytest.mark.parametrize("state", sorted(tick.FACES))
def test_the_frame_never_shifts(state):
    """Padding widths are load-bearing: every state must be the same shape."""
    art = tick.render(state, say=False)
    idle = tick.render("idle", say=False)
    assert [len(line) for line in art.splitlines()] == [
        len(line) for line in idle.splitlines()
    ]


def test_slot_widths_are_fixed():
    for face in tick.FACES.values():
        assert len(face["eyes"]) == 8
        assert len(face["mouth"]) == 4
        assert len(face["belly"]) == 7


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        (Session(json_out=True), False),
        (Session(quiet=True), False),
    ],
)
def test_mascot_suppressed_for_machines(session, expected):
    assert session.mascot_enabled is expected


def test_mascot_suppressed_by_env(monkeypatch):
    monkeypatch.setenv("APG_NO_MASCOT", "1")
    assert Session().mascot_enabled is False


def test_show_mascot_prints_nothing_when_suppressed(capsys):
    from apg.console import show_mascot

    show_mascot(Session(quiet=True), "idle")
    assert capsys.readouterr().out == ""

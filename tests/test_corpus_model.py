"""AS numbers, and the shapes a parsed standard takes."""

from __future__ import annotations

import pytest

from apg.corpus.model import (
    Paragraph,
    Section,
    Standard,
    as_slug,
    normalize_as_number,
    series_of,
)


@pytest.mark.parametrize(
    "typed",
    ["AS 2301", "AS2301", "as2301", "as 2301", "AS-2301", "as_2301", "2301", " 2301 "],
)
def test_every_way_a_person_writes_an_as_number_normalises(typed):
    """The prompt must not care how the user spells it."""
    assert normalize_as_number(typed) == "AS 2301"


@pytest.mark.parametrize("typed", ["", "AS", "23", "23011", "AS 23a1", "nonsense"])
def test_nonsense_is_refused(typed):
    with pytest.raises(ValueError):
        normalize_as_number(typed)


def test_slug_is_the_filename_form():
    assert as_slug("AS 2301") == "AS2301"


@pytest.mark.parametrize(
    ("as_number", "expected"),
    [
        ("AS 1000", "General Auditing Standards"),
        ("AS 2301", "Audit Procedures"),
        ("AS 3101", "Auditor Reporting"),
        ("AS 4105", "Federal Securities Filings"),
        ("AS 6115", "Other Audit-Related Matters"),
    ],
)
def test_series_follows_the_pcaob_grouping(as_number, expected):
    assert series_of(as_number) == expected


def _standard() -> Standard:
    return Standard(
        as_number="AS 2301",
        title="The Auditor's Responses",
        url="https://example.invalid/AS2301",
        sections=(
            Section("Introduction", 2, (Paragraph(".01", "First."),)),
            Section("Objective", 2, (Paragraph(".02", "Second."),)),
        ),
        footnotes=(Paragraph("1", "A footnote."),),
    )


def test_paragraph_count_spans_every_section():
    assert _standard().paragraph_count == 2


def test_paragraphs_keeps_each_paragraph_with_its_section():
    pairs = _standard().paragraphs()
    assert [(s.heading, p.number) for s, p in pairs] == [
        ("Introduction", ".01"),
        ("Objective", ".02"),
    ]


def test_round_trip_through_a_dict_loses_nothing():
    """The JSON on disk must reconstruct exactly, or the corpus is not pinned."""
    original = _standard()
    assert Standard.from_dict(original.to_dict()) == original


def test_to_text_carries_the_numbers_and_headings():
    text = _standard().to_text()
    assert "AS 2301: The Auditor's Responses" in text
    assert "Introduction" in text
    assert ".01  First." in text
    assert "Footnotes" in text

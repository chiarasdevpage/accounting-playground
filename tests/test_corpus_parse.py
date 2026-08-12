"""The parser, checked against real saved PCAOB pages.

These assertions are deliberately specific — ".11A exists", "54 paragraphs",
"no stray footnote digits". A parser that silently starts dropping content still
produces plausible-looking output, and the only way to notice is to pin down what
the real page actually contains.
"""

from __future__ import annotations

import re

import pytest

from apg.corpus.parse import ParseError, clean, parse_standard


@pytest.fixture
def as2301(as2301_html):
    return parse_standard(as2301_html, url="https://example.invalid/AS2301")


def test_title_and_number_come_off_the_heading(as2301):
    assert as2301.as_number == "AS 2301"
    assert as2301.title == (
        "The Auditor's Responses to the Risks of Material Misstatement"
    )


def test_the_whole_standard_is_present(as2301):
    assert as2301.paragraph_count == 54
    assert len(as2301.sections) == 23
    assert len(as2301.footnotes) == 29


def test_headings_keep_their_nesting(as2301):
    headings = {(s.heading, s.level) for s in as2301.sections}
    assert ("Introduction", 2) in headings
    assert ("Responses to Fraud Risks", 3) in headings


def test_paragraph_numbers_run_from_01_and_include_the_appendix(as2301):
    numbers = [p.number for _, p in as2301.paragraphs()]
    assert numbers[0] == ".01"
    assert ".50" in numbers
    # Appendix paragraphs are lettered, and are the reason the number pattern
    # cannot simply be two digits.
    assert numbers[-3:] == [".A1", ".A2", ".A3"]


def test_an_inserted_paragraph_keeps_its_letter(as2301):
    """AS 2301 .11A was inserted between .11 and .12; it is not ".11"."""
    numbers = [p.number for _, p in as2301.paragraphs()]
    assert ".11A" in numbers


def test_a_paragraph_absorbs_the_list_beneath_it(as2301):
    """.04 is one sentence followed by a lettered list; the list is the content."""
    para = next(p for _, p in as2301.paragraphs() if p.number == ".04")
    assert "types of audit responses" in para.text
    assert "overall responses" in para.text
    assert "nature, timing, and extent" in para.text


def test_a_note_block_stays_with_its_paragraph(as2301):
    para = next(p for _, p in as2301.paragraphs() if p.number == ".09")
    assert "Note:" in para.text


def test_footnotes_are_separated_from_the_running_text(as2301):
    assert as2301.footnotes[0].number == "1A"
    assert "engagement team" in as2301.footnotes[0].text
    body = " ".join(p.text for _, p in as2301.paragraphs())
    # The marker digits belong to the footnotes, not mid-sentence in the body.
    assert not re.search(r"procedures\. \d+ Paragraphs", body)


def test_the_summary_table_of_contents_is_not_treated_as_content(as2301):
    """The page repeats its headings in a bookmark list; parsing it would duplicate."""
    intro = next(s for s in as2301.sections if s.heading == "Introduction")
    assert len(intro.paragraphs) == 1


def test_no_invisible_characters_survive(as2301):
    body = " ".join(p.text for _, p in as2301.paragraphs())
    assert "\xa0" not in body
    assert "​" not in body
    assert "�" not in body


def test_paragraph_ranges_are_not_broken_apart_by_markup(as2301):
    """The source wraps hyphens in <span>; ".05-.07" must not become ".05 - .07"."""
    body = " ".join(p.text for _, p in as2301.paragraphs())
    assert ".05-.07" in body
    assert not re.search(r"\d - \.\d", body)


def test_front_matter_is_kept_as_provenance_not_as_a_paragraph(as2301):
    assert any("Adopting Release" in note for note in as2301.notes)
    body = " ".join(p.text for _, p in as2301.paragraphs())
    assert "Adopting Release" not in body


def test_a_short_standard_parses_too(as3110_html):
    """AS 3110 is a few paragraphs with almost no structure."""
    standard = parse_standard(as3110_html)
    assert standard.as_number == "AS 3110"
    assert standard.paragraph_count >= 1


def test_a_standard_with_no_headings_is_not_dropped(as1110_html):
    """The regression that cost four standards on the first real download.

    AS 1110, AS 1305, AS 2710 and AS 2905 have no <h2> at all. A parser that
    only emitted a section once it had seen a heading threw all of their
    paragraphs away and reported "no numbered paragraphs found" — a failure that
    looked like a broken page rather than a broken parser.
    """
    standard = parse_standard(as1110_html)
    assert standard.as_number == "AS 1110"
    assert standard.paragraph_count == 3
    assert len(standard.sections) == 1
    # With no heading of its own, the run is filed under the standard's title.
    assert standard.sections[0].heading == standard.title


def test_a_rescission_notice_is_kept_as_provenance(as1110_html):
    """AS 1110 is scheduled for rescission; a corpus that hides that is misleading."""
    standard = parse_standard(as1110_html)
    assert any("rescinded" in note for note in standard.notes)


def test_a_page_that_is_not_a_standard_is_refused():
    with pytest.raises(ParseError):
        parse_standard("<html><body><p>hello</p></body></html>")


def test_a_standard_with_no_paragraphs_is_refused():
    html = """
    <article class="article-detail">
      <h1 class="article-detail__title">AS 9999: Nothing Here</h1>
      <div class="article-detail__content"><h2>Introduction</h2></div>
    </article>
    """
    with pytest.raises(ParseError, match="no numbered paragraphs"):
        parse_standard(html)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\xa0\xa0b", "a b"),
        ("  spaced   out  ", "spaced out"),
        ("responsibilities .", "responsibilities."),
        ("( See paragraph )", "(See paragraph)"),
        # The space in a paragraph reference is correct and must survive.
        ("paragraphs .05 and .07", "paragraphs .05 and .07"),
    ],
)
def test_clean_tidies_markup_seams_without_eating_real_spacing(raw, expected):
    assert clean(raw) == expected

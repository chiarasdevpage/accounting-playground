"""Turning one downloaded page into a `Standard`.

Plain-English picture: the web page has a title, headings, and numbered
paragraphs (".01", ".02", ...). This pulls exactly those out and throws away the
navigation, the search box, the cookie banner and the footer.

Two details are load-bearing, and both were checked against the real pages rather
than assumed:

* **Numbered paragraphs are the unit that matters.** A citation like "AS 2301.09"
  points at one, so a paragraph must survive parsing intact and keep its number.
* **Not every block of text carries a number.** "Note:" blocks and lettered lists
  sit underneath the paragraph they belong to and are unmistakably part of it —
  AS 2301 .09 is a sentence followed by a list, and dropping the list would leave
  a requirement that no longer says what it requires. Unnumbered blocks are
  therefore appended to the paragraph above them, never discarded.
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, Tag

from apg.corpus.model import Paragraph, Section, Standard, normalize_as_number

# The blocks worth reading. Everything else on the page is furniture.
_BLOCK_TAGS = ("h2", "h3", "h4", "h5", "h6", "p", "li")
_HEADING_TAGS = {"h2", "h3", "h4", "h5", "h6"}

# ".01", ".11A" (an inserted paragraph), ".A1" (an appendix paragraph).
_PARAGRAPH_NUMBER = re.compile(r"^\.(\d{2}[A-Z]?|[A-Z]\d+)(?=\s|$)")

_TITLE_SPLIT = re.compile(
    r"^\s*(AS\s*\d{4})\s*[:—-]\s*(.+)$", re.IGNORECASE | re.DOTALL
)


class ParseError(ValueError):
    """The page did not look like an auditing standard."""


def clean(text: str) -> str:
    """Collapse the page's whitespace and tidy the seams left by its markup.

    The source is full of non-breaking spaces — they are how it indents paragraph
    numbers — and they would otherwise travel all the way into the training data
    as invisible junk. NFKC folds them and the other typographic lookalikes down
    to plain characters.

    The two `sub`s afterwards repair spacing the page's own markup introduces: it
    wraps fragments in tags with real whitespace around them, so text arrives as
    "engagement responsibilities ." and "( See paragraphs". Note the guard on the
    first one — the space in "paragraphs .05" is correct and must survive, so a
    stop is only closed up when nothing follows it.
    """
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    text = re.sub(r" +([.,;:])(?=\s|$)", r"\1", text)
    return re.sub(r"\( +", "(", re.sub(r" +\)", ")", text))


def _is_nested(el: Tag) -> bool:
    """True if an ancestor is itself a block we will visit, to avoid double-reading."""
    return any(parent.name in _BLOCK_TAGS for parent in el.parents)


def _split_title(raw: str) -> tuple[str, str]:
    match = _TITLE_SPLIT.match(clean(raw))
    if match is None:
        raise ParseError(f"could not read an AS number from title {raw!r}")
    return normalize_as_number(match.group(1)), match.group(2).strip()


def _parse_footnotes(block: Tag) -> tuple[Paragraph, ...]:
    """Footnotes, each keyed by its marker ("1A", "2", ...)."""
    notes: list[Paragraph] = []
    for para in block.find_all("p"):
        marker = para.find("sup")
        number = clean(marker.get_text()) if marker else ""
        if marker:
            marker.extract()
        text = clean(para.get_text())
        if text:
            notes.append(Paragraph(number=number or "?", text=text))
    return tuple(notes)


def parse_standard(
    html: str,
    url: str = "",
    source_sha256: str = "",
    fetched_utc: str = "",
) -> Standard:
    """Parse one standard's page. Raises `ParseError` if it isn't one."""
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.select_one("h1.article-detail__title")
    if heading is None:
        raise ParseError("no standard title on the page")
    as_number, title = _split_title(heading.get_text())

    body = soup.select_one("div.article-detail__content")
    if body is None:
        raise ParseError(f"{as_number}: no standard body on the page")

    # The summary table of contents just repeats the headings below it, and the
    # footnotes are their own block rather than part of the running text.
    for bookmarks in body.select("ul.standardTopBookmarks"):
        bookmarks.extract()
    footnote_block = body.select_one("div.footnotes")
    footnotes = _parse_footnotes(footnote_block.extract()) if footnote_block else ()

    # Footnote *references* in the running text are bare superscript numbers.
    # Rendered flat they become stray digits mid-sentence ("...substantive
    # procedures. 9 Paragraphs .16-.35 discuss..."), which reads like part of a
    # citation and would be learned as one. The footnotes themselves are kept
    # above, so nothing is lost by dropping the markers.
    for marker in body.find_all("sup"):
        marker.extract()

    sections: list[Section] = []
    notes: list[str] = []
    current_heading: str | None = None
    current_level = 2
    paragraphs: list[Paragraph] = []
    pending: list[str] = []  # text of the paragraph being accumulated
    pending_number: str | None = None

    def close_paragraph() -> None:
        nonlocal pending, pending_number
        if pending_number is not None:
            paragraphs.append(
                Paragraph(number=pending_number, text=" ".join(pending).strip())
            )
        pending = []
        pending_number = None

    def close_section() -> None:
        nonlocal paragraphs
        close_paragraph()
        if paragraphs:
            sections.append(
                Section(
                    # The short standards — AS 1110, AS 1305, AS 2710, AS 2905 —
                    # have no headings at all: three or four paragraphs sit
                    # directly under the title. Requiring a heading dropped them
                    # entirely, so an unheaded run is filed under the standard's
                    # own title rather than discarded.
                    heading=current_heading or title,
                    level=current_level,
                    paragraphs=tuple(paragraphs),
                )
            )
        paragraphs = []

    for el in body.find_all(_BLOCK_TAGS):
        if _is_nested(el):
            continue
        text = clean(el.get_text())
        if not text:
            continue

        if el.name in _HEADING_TAGS:
            close_section()
            current_heading = text
            current_level = int(el.name[1])
            continue

        match = _PARAGRAPH_NUMBER.match(text)
        if match:
            close_paragraph()
            pending_number = f".{match.group(1)}"
            pending = [text[match.end() :].strip()]
        elif pending_number is not None:
            # A "Note:" or a list item belonging to the paragraph above.
            pending.append(text)
        elif current_heading is None:
            # Front matter above the first heading: the adopting release and
            # amendment history. Provenance worth keeping, but not standard text.
            notes.append(text)

    close_section()

    if not sections:
        raise ParseError(f"{as_number}: no numbered paragraphs found")

    return Standard(
        as_number=as_number,
        title=title,
        url=url,
        sections=tuple(sections),
        footnotes=footnotes,
        source_sha256=source_sha256,
        fetched_utc=fetched_utc,
        notes=tuple(notes),
    )


__all__ = ["ParseError", "clean", "parse_standard"]

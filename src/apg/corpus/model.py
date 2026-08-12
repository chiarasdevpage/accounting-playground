"""The shapes a parsed auditing standard takes.

Plain-English picture: a standard is a title plus a list of sections; a section
is a heading plus a list of numbered paragraphs. That structure is the whole
point of parsing rather than saving a wall of text — Phase 3 generates questions
one section at a time, and Phase 6 checks that a model's citation names a
paragraph that genuinely exists.

`normalize_as_number` lives here rather than in a command because the canonical
form it produces ("AS 2301") is the citation format the grader will string-match
on. One definition, used by the parser, the store, and every command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Matches the ways a person or a web page writes an AS number: "AS 2301",
# "AS2301", "as-2301", or just "2301". The number itself is always four digits.
_AS_PATTERN = re.compile(r"^\s*(?:as[\s\-_]*)?(\d{4})\s*$", re.IGNORECASE)


def normalize_as_number(value: str) -> str:
    """Return the canonical `"AS 2301"` form, or raise ValueError.

    Accepts every spelling a user might type at the prompt. Raising rather than
    returning None is deliberate: callers turn this into an `ApgError` with a
    usage hint, and a silent None would surface later as a confusing "not found".
    """
    match = _AS_PATTERN.match(value or "")
    if match is None:
        raise ValueError(f"{value!r} is not an AS number")
    return f"AS {match.group(1)}"


def as_slug(as_number: str) -> str:
    """Filename form: `"AS 2301"` -> `"AS2301"`."""
    return as_number.replace(" ", "")


def series_of(as_number: str) -> str:
    """The PCAOB grouping an AS number belongs to.

    The thousands digit is the category, and the site organises its index the
    same way. `corpus list` groups by this so 51 rows read as five short tables.
    """
    digit = as_number.split()[-1][0]
    return {
        "1": "General Auditing Standards",
        "2": "Audit Procedures",
        "3": "Auditor Reporting",
        "4": "Federal Securities Filings",
        "6": "Other Audit-Related Matters",
    }.get(digit, "Other")


@dataclass(frozen=True)
class Paragraph:
    """One numbered paragraph. `number` is ".01", or ".A1" inside an appendix."""

    number: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"number": self.number, "text": self.text}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Paragraph:
        return cls(number=raw["number"], text=raw["text"])


@dataclass(frozen=True)
class Section:
    """A heading and the paragraphs beneath it.

    `level` is 2 for a top-level section and 3 for a subsection, mirroring the
    source page's own <h2>/<h3> nesting.
    """

    heading: str
    level: int
    paragraphs: tuple[Paragraph, ...] = ()

    @property
    def text(self) -> str:
        """The section rendered as plain text, heading included."""
        lines = [self.heading]
        lines.extend(f"{p.number}  {p.text}" for p in self.paragraphs)
        return "\n\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "level": self.level,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Section:
        return cls(
            heading=raw["heading"],
            level=raw["level"],
            paragraphs=tuple(Paragraph.from_dict(p) for p in raw["paragraphs"]),
        )


@dataclass(frozen=True)
class Standard:
    """One auditing standard, parsed."""

    as_number: str
    title: str
    url: str
    sections: tuple[Section, ...] = ()
    footnotes: tuple[Paragraph, ...] = ()
    source_sha256: str = ""
    fetched_utc: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def paragraph_count(self) -> int:
        return sum(len(s.paragraphs) for s in self.sections)

    @property
    def series(self) -> str:
        return series_of(self.as_number)

    @property
    def slug(self) -> str:
        return as_slug(self.as_number)

    def paragraphs(self) -> list[tuple[Section, Paragraph]]:
        """Every paragraph with the section it came from — what search iterates."""
        return [(s, p) for s in self.sections for p in s.paragraphs]

    def to_text(self) -> str:
        """The readable rendering saved as `.txt` and printed by `corpus show`."""
        parts = [f"{self.as_number}: {self.title}", f"Source: {self.url}", ""]
        parts.extend(s.text for s in self.sections)
        if self.footnotes:
            parts.append("Footnotes")
            parts.extend(f"{f.number}  {f.text}" for f in self.footnotes)
        return "\n\n".join(parts).strip() + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_number": self.as_number,
            "title": self.title,
            "url": self.url,
            "series": self.series,
            "source_sha256": self.source_sha256,
            "fetched_utc": self.fetched_utc,
            "notes": list(self.notes),
            "sections": [s.to_dict() for s in self.sections],
            "footnotes": [f.to_dict() for f in self.footnotes],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Standard:
        return cls(
            as_number=raw["as_number"],
            title=raw["title"],
            url=raw["url"],
            sections=tuple(Section.from_dict(s) for s in raw["sections"]),
            footnotes=tuple(Paragraph.from_dict(f) for f in raw.get("footnotes", [])),
            source_sha256=raw.get("source_sha256", ""),
            fetched_utc=raw.get("fetched_utc", ""),
            notes=tuple(raw.get("notes", ())),
        )


__all__ = [
    "Paragraph",
    "Section",
    "Standard",
    "as_slug",
    "normalize_as_number",
    "series_of",
]

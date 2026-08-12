"""Which standards exist, and where each one lives.

Plain-English picture: before downloading anything we read the PCAOB's own index
page and take the list of standards from it.

That list is deliberately *not* hardcoded. The site's URLs are inconsistent —
most are tidy ("/details/AS1101") but several are long slugs
("/details/as-2101-audit-planning-2022"), and the pattern differs per standard
with no rule behind it. A hardcoded table would also silently go stale the day
the PCAOB adds or renumbers a standard, which is exactly the kind of quiet drift
this project's pinning rules exist to prevent. Scraping the index means the
manifest records what the site actually published on the day we looked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from apg.corpus.model import normalize_as_number, series_of

INDEX_URL = "https://pcaobus.org/oversight/standards/auditing-standards"

# Link text on the index reads "AS 2301: The Auditor's Responses to ...".
_LINK_TEXT = re.compile(r"^\s*(AS\s*\d{4})\s*[:—-]\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class StandardRef:
    """A standard as the index page advertises it, before anything is downloaded."""

    as_number: str
    title: str
    url: str

    @property
    def series(self) -> str:
        return series_of(self.as_number)


def parse_index(html: str, base_url: str = INDEX_URL) -> list[StandardRef]:
    """Every standard linked from the index page, sorted by AS number.

    Duplicates are expected — the page links some standards from both a topic
    list and a navigation rail — and are collapsed by URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, StandardRef] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/auditing-standards/details/" not in href:
            continue
        match = _LINK_TEXT.match(anchor.get_text(" ", strip=True))
        if match is None:
            continue
        try:
            as_number = normalize_as_number(match.group(1))
        except ValueError:
            continue
        # Keep the first sighting: the main content list comes before the nav
        # rail, and its titles are the full ones.
        found.setdefault(
            as_number,
            StandardRef(
                as_number=as_number,
                title=match.group(2).strip(),
                url=urljoin(base_url, href),
            ),
        )

    return sorted(found.values(), key=lambda ref: ref.as_number)


__all__ = ["INDEX_URL", "StandardRef", "parse_index"]

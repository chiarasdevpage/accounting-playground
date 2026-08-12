"""The PCAOB auditing standards corpus — download, parse, store, read.

Plain-English picture: this package turns 51 web pages on pcaobus.org into clean
text on your disk, and records exactly what it downloaded so the result can be
proved identical later. Reproducibility is a project ground rule, and a corpus
that quietly changes underneath the experiments would invalidate every score the
bench produces.

The pieces, in the order they run:

    source.py  which standards exist, and their URLs (scraped, never hardcoded)
    fetch.py   getting the pages, politely
    parse.py   HTML -> Standard
    store.py   Standard -> disk, plus the manifest that pins it
    model.py   the shapes everything above passes around

Nothing here imports from `apg.commands`; the commands import this.
"""

from __future__ import annotations

from apg.corpus.model import Paragraph, Section, Standard, normalize_as_number

__all__ = ["Paragraph", "Section", "Standard", "normalize_as_number"]

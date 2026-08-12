"""The `corpus` commands — download the standards, then look at them.

Plain-English picture: `corpus download` goes and gets the PCAOB's auditing
standards; the other four let you check what arrived and read it.

Nothing in this file parses HTML or touches the network directly. It calls into
`apg.corpus` and turns the result into a table, which is the same division every
command in this app follows: the logic is testable without a terminal, and the
presentation is testable without the internet.
"""

from __future__ import annotations

from apg.console import build_table, emit, say, show_mascot
from apg.corpus import store
from apg.corpus.model import normalize_as_number, series_of
from apg.errors import ApgError
from apg.registry import Param, command
from apg.session import Session

_NO_CORPUS = ApgError(
    "no corpus downloaded yet",
    hint="run `corpus download` (about a minute, needs the internet)",
)

# Series order for `corpus list` — the PCAOB's own grouping, not numeric order,
# so the table reads the way their index page does.
_SERIES_ORDER = (
    "General Auditing Standards",
    "Audit Procedures",
    "Auditor Reporting",
    "Federal Securities Filings",
    "Other Audit-Related Matters",
    "Other",
)


def _require_corpus() -> store.Corpus:
    corpus = store.load_corpus()
    if corpus is None:
        raise _NO_CORPUS
    return corpus


def _as_number(value: str) -> str:
    try:
        return normalize_as_number(value)
    except ValueError as exc:
        raise ApgError(
            f"{value!r} is not an AS number",
            hint="try: corpus show 2301, or `corpus list` to see them all",
        ) from exc


@command("corpus download", "Download the PCAOB auditing standards from pcaobus.org.")
def corpus_download(session: Session) -> None:
    # Imported here rather than at module scope: importing this command module
    # must not pull in an HTTP stack, because `apg --help` imports every command
    # and the test suite asserts that help never touches the network.
    from apg.console import progress
    from apg.corpus import download as downloader
    from apg.corpus.fetch import make_client

    say(session, "reading the standards index from pcaobus.org ...", style="dim")
    show_mascot(session, "sleepy")

    client = make_client()
    try:
        refs = downloader.read_index(client)
        say(session, f"{len(refs)} standards to fetch.", style="dim")

        with progress(session, total=len(refs), description="downloading") as bar:
            # The callback fires *before* each fetch, so it advances for the
            # request that just finished, not the one about to start.
            def tick(position: int, total: int, ref) -> None:
                bar.advance(0 if position == 1 else 1, ref.as_number)

            result = downloader.fetch_all(client, refs, on_progress=tick)
            bar.advance(1)
    finally:
        client.close()

    for as_number, reason in result.failures:
        say(session, f"skipped {as_number}: {reason}", style="yellow")

    payload = {
        "version": result.version,
        "path": str(result.root),
        "standards": len(result.standards),
        "paragraphs": result.paragraph_count,
        "fingerprint": result.manifest.get("fingerprint", ""),
        "failures": [{"as_number": n, "reason": r} for n, r in result.failures],
    }
    rows = [
        ["version", result.version],
        ["standards", len(result.standards)],
        ["paragraphs", result.paragraph_count],
        ["skipped", len(result.failures)],
        ["saved to", str(result.root)],
    ]
    emit(session, payload, build_table("downloaded", ["item", "value"], rows))

    # The session was created before the corpus existed; refresh it so the status
    # strip updates without the user having to restart the shell.
    session.corpus_version = result.version


@command("corpus status", "Show which corpus is downloaded, and when it was pinned.")
def corpus_status(session: Session) -> None:
    corpus = _require_corpus()
    payload = {
        "corpus": corpus.manifest.get("corpus", store.CORPUS_NAME),
        "version": corpus.version,
        "downloaded_utc": corpus.downloaded_utc,
        "standards": corpus.standard_count,
        "paragraphs": corpus.paragraph_count,
        "fingerprint": corpus.fingerprint,
        "source_index": corpus.manifest.get("source_index", ""),
        "path": str(corpus.root),
    }
    rows = [
        ["corpus", payload["corpus"]],
        ["version", corpus.version],
        ["downloaded", corpus.downloaded_utc],
        ["standards", corpus.standard_count],
        ["paragraphs", corpus.paragraph_count],
        ["fingerprint", corpus.fingerprint],
        ["path", str(corpus.root)],
    ]
    emit(
        session,
        payload,
        build_table("corpus status", ["item", "value"], rows, keep_whole=["value"]),
    )
    for note in corpus.manifest.get("notes", []):
        say(session, f"note: {note}", style="dim")


@command("corpus list", "List every standard in the downloaded corpus.")
def corpus_list(session: Session) -> None:
    corpus = _require_corpus()

    def position(entry: dict) -> tuple[int, str]:
        series = entry.get("series") or series_of(entry["as_number"])
        rank = (
            _SERIES_ORDER.index(series)
            if series in _SERIES_ORDER
            else len(_SERIES_ORDER)
        )
        return rank, entry["as_number"]

    entries = sorted(corpus.entries, key=position)
    payload = {"version": corpus.version, "standards": entries}
    rows = [
        [
            e["as_number"],
            e["title"],
            e.get("series", ""),
            e.get("paragraphs", 0),
        ]
        for e in entries
    ]
    emit(
        session,
        payload,
        build_table(
            f"{corpus.standard_count} standards - corpus {corpus.version}",
            ["standard", "title", "series", "paragraphs"],
            rows,
            numeric=["paragraphs"],
            keep_whole=["standard"],
        ),
    )


@command(
    "corpus show",
    "Print one auditing standard.",
    params=(Param("as_number", "e.g. 2301, AS 2301", rest=True),),
)
def corpus_show(session: Session, as_number: str) -> None:
    corpus = _require_corpus()
    canonical = _as_number(as_number)
    if not corpus.has(canonical):
        raise ApgError(
            f"{canonical} is not in the downloaded corpus",
            hint="run `corpus list` to see what is",
        )
    standard = corpus.load(canonical)

    if session.json_out:
        emit(session, standard.to_dict())
        return

    # Deliberately not a table: this is a page of prose, and a bordered cell
    # would wrap it into something unreadable.
    console = session.console
    console.print(f"{standard.as_number}: {standard.title}", style="bold")
    console.print(standard.url, style="dim")
    for section in standard.sections:
        console.print("")
        console.print(section.heading, style="bold")
        for paragraph in section.paragraphs:
            console.print(f"{paragraph.number}  {paragraph.text}")
    if standard.footnotes:
        console.print("")
        console.print("Footnotes", style="bold")
        for note in standard.footnotes:
            console.print(f"{note.number}  {note.text}", style="dim")


@command(
    "corpus search",
    "Find paragraphs mentioning a word or phrase.",
    params=(Param("term", "a word or phrase", rest=True),),
)
def corpus_search(session: Session, term: str) -> None:
    corpus = _require_corpus()
    needle = term.strip().lower()
    if not needle:
        raise ApgError("nothing to search for", hint="usage: corpus search <term...>")

    hits = []
    for standard in corpus.load_all():
        for section, paragraph in standard.paragraphs():
            if needle in paragraph.text.lower():
                hits.append(
                    {
                        "as_number": standard.as_number,
                        "paragraph": paragraph.number,
                        "heading": section.heading,
                        "text": paragraph.text,
                    }
                )

    payload = {"term": term, "matches": len(hits), "hits": hits}
    if not hits:
        emit(session, payload, build_table(f"no matches for {term!r}", ["result"], []))
        say(session, "nothing matched. try a shorter phrase.", style="dim")
        return

    rows = [
        [h["as_number"], h["paragraph"], _excerpt(h["text"], needle)] for h in hits
    ]
    emit(
        session,
        payload,
        build_table(
            f"{len(hits)} matches for {term!r}",
            ["standard", "paragraph", "text"],
            rows,
            keep_whole=["standard", "paragraph"],
        ),
    )


def _excerpt(text: str, needle: str, width: int = 140) -> str:
    """A window of `text` around the first match, so the hit is visible in the row."""
    if len(text) <= width:
        return text
    position = text.lower().find(needle)
    start = max(0, position - width // 3)
    excerpt = text[start : start + width]
    return ("..." if start else "") + excerpt.strip() + "..."

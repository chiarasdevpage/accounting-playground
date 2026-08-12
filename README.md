# Accounting Playground

A testing ground for accounting assistants. The first experiment is an **audit
standards specialist bench**: fine-tune several small open LLMs on PCAOB auditing
standards, benchmark them against each other with a rubric, and ship the whole
thing inside a terminal app.

> **Not professional advice.** This is a research and education artifact. No model
> here is a trustworthy audit or tax advisor, and none of its output should be
> relied on for professional work.

## Status

**Phase 2 of 8 — the corpus.** The shell works and it now has something to read:
all 51 current PCAOB auditing standards, downloaded, parsed, and pinned. There is
no dataset and no model yet.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run apg
```

Or install the `apg` command globally:

```
uv tool install --editable .
apg
```

## Use

Typing `apg` with no arguments opens the interactive shell:

```
apg> help
apg> status
apg> exit
```

Every command also works as a one-shot from your regular shell:

```
apg status
apg status --json
```

### The corpus

Download the standards once — about a minute, and it needs the internet:

```
apg corpus download
```

Then look around:

```
apg corpus status                        what is downloaded, and its checksum
apg corpus list                          all 51 standards, grouped by series
apg corpus show 2301                     print one standard
apg corpus search professional skepticism
```

`corpus show` and `corpus search` take the rest of the line, so quotes are
optional — `corpus show AS 2301`, `corpus show 2301` and `corpus show "AS 2301"`
are the same command.

Everything lands in `data/corpus/<version>/`, which is gitignored (8.6 MB):

| | |
|---|---|
| `raw/AS2301.html` | the page exactly as the server sent it |
| `json/AS2301.json` | sections, numbered paragraphs, footnotes |
| `text/AS2301.txt` | readable plain text |
| `manifest.json` | what was downloaded, when, and a SHA-256 of every page |

The raw HTML is kept deliberately: if the parser needs fixing, the corpus can be
rebuilt from disk without going back to pcaobus.org and without any risk the site
changed in between.

### How the corpus is pinned

`manifest.json` records the download date, the source URL, a SHA-256 per page,
and a `fingerprint` — a single checksum standing for the whole corpus. Two runs
reporting the same fingerprint read exactly the same text; two runs reporting
different fingerprints are not comparable, and any scores drawn from them are
not either.

The August 2026 snapshot: **51 standards, 1,494 numbered paragraphs**,
fingerprint `sha256:7c9085f0…24b767bb`.

Known limitations, recorded in the manifest itself:

- The PCAOB phases amendments in by fiscal year. These pages carry whatever text
  was effective on the download date, which is not necessarily the text that
  governs any particular audit. AS 1110, for one, is scheduled for rescission in
  December 2026; that notice is preserved in its record.
- Lists inside a paragraph are flattened into the paragraph's prose. Nothing is
  lost, but the boundaries between list items are not marked.
- Footnote text is kept separately from the paragraph that referenced it; the
  reference markers are not retained inline.

These are not two implementations. Both surfaces dispatch into the same registry
of functions (`src/apg/registry.py`), which is the rule the project is built
around — see "One command registry" in `PROJECT-PLAN.md`.

### Global flags

| Flag | Effect |
|---|---|
| `--json` | Machine-readable output only. No colour, no mascot. |
| `--quiet` | Suppress chatter and colour. |
| `--no-color` | Strip ANSI styling, keep the prose. |
| `--debug` | Show full tracebacks instead of one-line explanations. |

`APG_NO_MASCOT=1` retires Tick without changing anything else.

## Development

```
uv run pytest
uv run ruff check .
```

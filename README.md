# Accounting Playground

A testing ground for accounting assistants. The first experiment is an **audit
standards specialist bench**: fine-tune several small open LLMs on PCAOB auditing
standards, benchmark them against each other with a rubric, and ship the whole
thing inside a terminal app.

> **Not professional advice.** This is a research and education artifact. No model
> here is a trustworthy audit or tax advisor, and none of its output should be
> relied on for professional work.

## Status

**Phase 1 of 8 — the TUI skeleton.** The shell exists; the science does not yet.
`help`, `status`, and `exit` work. There is no corpus, no dataset, and no model.

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

---
name: project-accounting-playground
description: "Accounting Playground — bench for fine-tuning small LLMs on PCAOB audit standards, shipped as the `apg` terminal app; Phase 2 of 8 (corpus) done 2026-08-12 on an unpushed branch, awaiting approval for Phase 3"
metadata: 
  node_type: memory
  type: project
  originSessionId: d93f48f4-cc72-46b6-9ebc-37f515af179a
  modified: 2026-08-12T03:07:00.792Z
---

**Accounting Playground** — a testing ground for accounting assistants. Experiment
#1 is an audit standards specialist bench: QLoRA fine-tune 4–5 small open models
(Qwen 2.5-3B, Llama 3.2 3B, Gemma 2B/4B, Phi-4-mini, optional 1B control) on the
PCAOB AS series (AS 1000–4105), grade them with a blind Claude judge, publish an
honest leaderboard. Free tier only (Colab GPU for training, GGUF for local CPU
inference). Explicitly NOT a production audit advisor.

## WHERE WE ARE (2026-08-12)

**Phase 2 of 8 COMPLETE — the corpus.** 184 tests green, ruff clean. Eight
commands work: `help` / `status` / `exit` plus `corpus download` / `status` /
`list` / `show` / `search`. Real download ran end-to-end: **51 standards, 1,494
numbered paragraphs, 0 skipped**, 8.6 MB.

**Merged to `main` and pushed 2026-08-12** — main@7bd8375, local == origin/main,
fast-forward so there is no merge commit. The `phase-2-corpus` branch still
exists locally and is fully merged; deleting it is optional housekeeping.

**⏸️ PHASE 3 DEFERRED — WAITING ON THE BUILDER'S PAYCHECK (as of 2026-08-12).**
Dataset generation is the first phase that spends Anthropic API money, and they
chose to pay for it properly rather than take the free-but-less-reproducible
route. **They will say when they're ready — do not start Phase 3 unsolicited, and
do not nudge about the paycheck.** When they return, the first move is to confirm
the budget is actually there, then run a small pilot slice before the full run.

**⏳ Still open from Phase 1:** the builder's manual check of the interactive
shell in a real terminal (history, Tab completion, Ctrl-C, Ctrl-D). The harness
has no tty so it cannot be automated — `start()` deliberately prints the command
list instead of prompting when stdin/stdout isn't a terminal. Never reported back
across two sessions; ask.

## To resume

```
cd C:\Users\super\Projects\accounting-playground
uv sync
uv run pytest        # expect 184 passed
uv run ruff check .
uv run apg corpus status
```

- Repo: `C:\Users\super\Projects\accounting-playground`, private
  `ProjectBuilder67/accounting-playground`, **main@7bd8375 pushed and clean**.
- Full 8-phase plan: `PROJECT-PLAN.md` in the repo root (the builder's copy lives
  at `C:\Users\super\Downloads\PROJECT-PLAN_2.md`). Approved build plans:
  Phase 1 `robust-petting-bentley.md`, Phase 2
  `ok-open-c-users-super-downloads-project-elegant-zebra.md`, both under
  `C:\Users\super\.claude\plans\`.
- Boot command `apg`; package `apg`, src-layout; uv + hatchling + ruff;
  Python 3.12 x64. Deps still pure-Python — typer, rich, prompt_toolkit, plus
  httpx and beautifulsoup4 (used with stdlib `html.parser`, **no lxml**, which
  deliberately dodges [[env-windows-arm-python]]).

## The corpus (Phase 2 output)

Lives in `data/corpus/2026-08/` — **gitignored, so it is NOT recoverable from the
repo**; re-run `apg corpus download` (~1 min) on a fresh clone. Per standard:
`raw/*.html` (as the server sent it), `json/*.json` (structured), `text/*.txt`
(readable), plus `manifest.json`.

**Corpus pin, Aug 2026 snapshot:** 51 standards, 1,494 paragraphs, fingerprint
`sha256:7c9085f078b028def4dc978ecd76c640c2926802ac1050e2290f4be324b767bb`.
A later download reporting a different fingerprint means the standards moved and
scores across the two are not comparable — that is the whole point of the pin.

Scope is **all 51 standards including AS 6101–6115**, a deliberate widening of
the plan's "AS 1000–4105" that the builder approved. Storage shape (JSON + text +
raw HTML) was also their explicit choice over text-only.

**Raw HTML is kept on purpose:** `store.reparse(version)` rebuilds the whole
corpus from disk in seconds when the parser improves, with no network call and no
change to the fingerprint (which hashes the source pages, not the parsed output).

## Ground rules from the builder's plan

- **The builder is non-technical. Explain in plain terms and STOP FOR APPROVAL
  at every phase boundary.** This is written into the project plan, not inferred.
- Free tier only; pin everything (corpus version + download date, model versions,
  seeds, prompt templates) — reproducibility is the brand.
- Zero-shot baselines get scored BEFORE fine-tuning — that control group is what
  makes the leaderboard falsifiable.
- Two test sets, reported separately and never blended: ~10% random held-out
  questions (**memorization**) and 1–2 entire held-out standards
  (**generalization**, the harsh one). Expect these to diverge; if generalization
  flops that is the finding, not a bug — same posture as [[project-bipgpt]]'s
  honest negative result.

## The load-bearing design decision

**One command registry (`src/apg/registry.py`), two front ends.** Commands are
plain functions importing neither Typer nor prompt_toolkit;
`src/apg/dispatch.py` is the single shared parser plus a mode-aware error
boundary (`oneshot` exits non-zero, `repl` prints and returns to the prompt —
which matters once Phase 5's `use <model>` holds a warm multi-GB model).
`tests/test_registry.py` asserts the Typer command set == the registry, so a
parallel implementation cannot drift in later.

Params are **declared** (`Param(name, help, required, type)`), not inferred from
Python type hints, precisely so both surfaces parse identically by construction.

Phase 2 added **`Param(..., rest=True)`** — the last param swallows the remainder
of the line, so `corpus show AS 2301` works without quotes. **Phase 5's
`ask <question>` should use this**, not a bespoke workaround; that anticipated
second use is why it went into the dispatcher rather than into one command.

Adding a command in a later phase is one decorator plus one import line in
`src/apg/commands/__init__.py`; it then appears in the CLI, the shell, `help`,
and tab completion automatically.

**Why:** [[project-bipgpt]] attached commands straight to Typer with
`typer.Option(...)` baked into every signature — nothing but Typer can call them,
which is why `bip` has no REPL and never got one. Building the registry at three
trivial commands avoided that. See [[feedback-prefer-root-cause-fixes]].

## File map

`src/apg/`: `registry.py` (Command/Param/@command/resolve) · `dispatch.py`
(split/coerce/parse_args/run, `ExitSession`) · `session.py` (Session, flags +
live state + `state_summary()`) · `console.py` (UTF-8 hardening, `emit`/`say`,
`build_table`, `show_mascot`) · `errors.py` (`ApgError`, hints, `report`) ·
`tick.py` (mascot) · `repl.py` (prompt_toolkit loop, banner, status strip,
`RegistryCompleter`) · `cli.py` (Typer app generated from the registry) ·
`paths.py` (the ONLY place that builds a data path; `APG_DATA_DIR` overrides it,
which is how the tests stay off the real corpus) ·
`corpus/` (`model.py` Standard/Section/Paragraph + `normalize_as_number` ·
`source.py` index scrape · `fetch.py` httpx · `parse.py` HTML→Standard ·
`store.py` disk + manifest · `download.py` orchestration) ·
`commands/core.py` (help/status/exit) · `commands/corpus.py` (the five corpus
commands). The `corpus/` package imports no Rich/Typer/Session — it reports
progress through a callback — so it stays usable from a notebook or script.

## Gotchas already hit and fixed

- **Rich markup eats square brackets.** `help [command]` silently lost its
  brackets, and user text containing `[` would crash the render. Fixed with
  `markup=False` on the Session's Console (everything is styled via `style=`,
  never inline tags) plus `rich.markup.escape` on the docstrings Typer renders
  through its own separate console. Both are load-bearing; don't "simplify" them
  away.
- **Mascot is Tick**, the ledger critter (auditors "tick and tie"; the belly
  marks are those ticks). Same mechanism as Blip: one `_BODY` template, per-state
  slots at FIXED widths (eyes 8 / mouth 4 / belly 7 — a test enforces this),
  `render()` falls back to idle and never raises. Four states: idle / happy
  ("ties out") / dizzy ("that doesn't reconcile") / sleepy.
  **Do NOT copy Blip's art** — BipGPT's `blip.py` `_BODY` has a stray `$1` regex
  artifact on line 19 that renders in his body every time.
- Mascot suppressed under `--json`, `--quiet`, `APG_NO_MASCOT=1`, and non-TTY,
  via the single `show_mascot()` chokepoint.
- **A parser can "succeed" while silently dropping 8% of the corpus.** Four
  standards (AS 1110, 1305, 2710, 2905) carry no `<h2>` at all — paragraphs sit
  straight under the title — and the first parser, which only emitted a section
  once it had seen a heading, threw all four away and reported the download as
  fine. Only the real download caught it. **Lesson for Phases 3–6: assert on
  expected counts, not just on "no exception."** Regression test + real fixture
  now pin it.
- pcaobus.org specifics, all verified live: `robots.txt` is an empty
  `Disallow:` (scraping permitted); pages are server-rendered (no JS);
  `h1.article-detail__title` + `div.article-detail__content` are the selectors;
  detail URL slugs are **inconsistent** (`/AS1101` vs
  `/as-2101-audit-planning-2022`) with no derivable rule, which is why the index
  is scraped rather than the 51 URLs hardcoded.
- **`get_text(sep)` joins every text node with `sep`, not just tag boundaries.**
  Using `" "` injected spaces mid-sentence — the site wraps hyphens in `<span>`,
  so `.05-.07` became `.05 - .07` — and unwrapping inline tags does not help.
  The fix is `get_text()` with no separator plus a narrow punctuation tidy in
  `parse.clean()`. Footnote `<sup>` markers are stripped from the body too, or
  they land mid-sentence as bare digits that read like citations.

## Known risks for later phases (flagged, not yet hit)

- **Phase 5 local inference may not work on this machine.** GGUF inference needs
  `llama-cpp-python`, a native extension, on Windows-on-ARM running x64 Python
  under emulation — the exact setup that already broke polars and bun here. See
  [[env-windows-arm-python]]. Spike this before committing to "the TUI runs the
  models locally"; have a fallback ready.
- **Free Colab won't fit the training in one sitting.** Daily GPU cap plus
  disconnects vs. 4–5 QLoRA runs plus zero-shot baselines. Phase 5 needs
  resumable checkpoints/adapters to Google Drive from the start.
- Phase 3 (dataset generation, ~3,000–5,000 pairs) and Phase 6 (Claude judge) are
  the only phases that cost money via the Anthropic API. **Phase 3 is next**, so
  this is now live, not hypothetical. Sizing input: the corpus is 1,494 paragraphs
  across 51 standards; ~3–5k pairs means roughly 2–3 questions per paragraph.
  **Measured estimates (2026-08-12): Phase 3 ≈ $4 (Haiku) / $8 (Sonnet) / $21
  (Opus); Phase 6 incl. zero-shot baselines ≈ 2x that. Batch API halves it.**
  **⚠️ Note the plan's own wording:** "free tier only" is scoped to *training and
  inference* (Colab GPU, local GGUF) — the plan text for Phases 3 and 6 explicitly
  specifies "Claude (via API)". Not a contradiction, but the builder read it as a
  blanket no-spend rule, so **surface the API cost at the phase boundary, not
  mid-phase.**
- **✅ DECIDED 2026-08-12: pay for the real API; do NOT use the `claude -p`
  workaround.** The `claude -p` route would have made Phase 3 free (see
  [[ref-subscription-vs-api-billing]]), and the builder was offered it. They
  **declined on reproducibility grounds** — weaker parameter pinning, and a poor
  fit for Phase 6's blind randomized judging, outweighed the saving. Its slowness
  was explicitly a non-issue to them. **Do not re-propose `claude -p` for this
  project's dataset generation or judging** unless they raise it; the decision is
  made and it is the right one for a project whose brand is reproducibility.
  See [[feedback-rigor-over-cost]].
- **Effective dates are a standing corpus caveat, not a bug to fix.** PCAOB
  phases amendments in by fiscal year, so the pages carry whatever was effective
  on the download date; AS 1110 is scheduled for rescission in Dec 2026 and that
  notice is preserved in its record. Stated in `manifest.json` and the README.
  It belongs in the Phase 7 limitations section too.
- Known corpus imperfection, accepted deliberately: **lists inside a paragraph
  are flattened into that paragraph's prose** — nothing is lost, but item
  boundaries are unmarked. If Phase 3's generated questions come back mangled on
  list-heavy requirements, this is the first thing to revisit.

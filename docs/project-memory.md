# Accounting Playground — project handoff

Recorded 2026-09-21 after reviewing the repository, all eight recovered migration
files, and the user's corrections. The user accepted the reconstruction and
explicitly authorized preserving it. This is durable project context, not a
claim that an assistant will remember a previous chat without reading files.

## Read first: monetary rules and responsibility

[AGENTS.md](../AGENTS.md) is the authoritative standing instruction file.
**Avoid spending unless genuinely necessary. Ask for explicit approval before
every payment or billable run, including prepaid API usage and auto mode.
Never exceed USD $10 total per session, even with approval.** Include incurred
costs, retries, parallel jobs, and outstanding commitments. Do not proceed when
maximum cost or remaining budget cannot be established; do not evade the ceiling
by splitting work or artificially restarting sessions.

The user clarified that this was the budget interpretation from the beginning.
Historical descriptions of paid generation as expected or implicitly authorized
are not permission to spend. Ownership of the project and approval to implement
features do not authorize billable work. These monetary rules are the user's
highest-priority project constraints and must not be violated.

The assistant is responsible for continuing the project, maintaining accurate
context, explaining work plainly, preserving experimental rigor, and respecting
phase boundaries. The user subsequently approved Phase 3 implementation as
described below. That approval authorizes neither billable runs nor later phases.

## GitHub publication checkpoint, 2026-09-22

The user explicitly requested committing and pushing all work so far to GitHub.
Destination: the verified private repository `chiarasdevpage/accounting-playground`,
branch `main`. Publication includes source, tests, configuration templates,
documentation, measurements and the recovered migration archive. Existing ignored
corpus data, generated datasets, model artifacts and environment files remain local.
Fresh verification: 239 pytest tests pass and Ruff passes. No paid calls were made.
This publication authorization does not authorize further implementation, paid
execution, or any change to the standing spending ceiling. See Git history for
the publication commit; the earlier local/uncommitted descriptions are historical.

## Latest user clarification: costs and authorization, 2026-09-21

The user considers $41.11 potentially acceptable ("isnt bad"), but explicitly
stated: **"we arent implementing or spending that money yet either way."**
The subsequent request to save this information authorizes documentation only.
Do not resume implementation or paid execution from this discussion. The $10
cumulative session ceiling remains unchanged. This is neither spending approval
nor authorization to evade the ceiling by splitting spending across sessions.

The cost breakdown is $10.62 production generation + $28.86 production semantic
criticism + $1.63 pilot generation/criticism = approximately $41.11 before
duplicate checks. Repeated full-standard context, especially one critic request
per candidate, drives input cost. The recovered Claude estimate assumed "the
corpus is ~400k tokens; Phase 3 reads it once" and discussed batch/cache discounts.
The exact earlier $11 estimate recalled by the user was not located; its
assumptions are not established. Current generation alone is about $11.

The $41.11 scenario assumes maximum candidate yield, 350 generated tokens per
candidate, 500 critic output tokens, four UTF-8 bytes per input token, and no
caching or batching. Doubling candidate length to 700 tokens gives about $44.65
before duplicates, with critic output unchanged. The discussed $41-45 is only
a scenario range, **not a total quote, spending cap or guaranteed range**.
Duplicate checks, longer critic responses, another pilot and regeneration can
increase costs. Actual token counts can move estimates either way. Lower yield
or measured caching might reduce cost, but neither is established savings.
No money was spent. See [cost details](phase-3b-costs.md).

## Latest update: Phase 3B free checkpoint, 2026-09-21

Implemented shared-registry `data estimate <config>` and `data verify <run_id>`,
settled-plus-outstanding invocation accounting, proven pre-submission failure
classification, and explicit unit/duplicate outcomes. The template now pins Haiku
4.5 for generator and critic; pricing verification placeholders remain pending.
See [supplied brief and execution plan](phase-3b-plan.md),
[cost checkpoint](phase-3b-costs.md) and [measurements](phase-3b-measurements.json).

**Outcome: defer paid work.** Heuristic pilot-plus-production cost is $41.1078
before duplicate criticism at candidate ceilings, 350 candidate output tokens and
500 critic output tokens. No API credential was present; exact token counts,
current pricing and account availability remain unverified. Even the supplied
optimistic cached scenario exceeds $10. No caching was implemented, no paid calls
were made, and no paid approval is requested. Implementation spending/commitments:
$0. Historical outside spending must still be reconciled before any future approval.

Verification: 239 pytest tests pass; Ruff passes. Tests use mocks and fixtures,
including verifier corruption checks and CLI/REPL JSON parity.

Phase 3 remains incomplete: no real pilot, human review, production or final
scientific completion exists. Gate 1 and Gate 2 remain closed. No Phase 4 work.

## Latest update: Phase 3 offline implementation, 2026-09-21

**User-approved scope:** implement the plan built from the supplied
[Phase 3 brief](phase-3-planning-brief.md). The user selected one standard per
example, a provisional 3,000–5,000 target, a separate Claude critic pass, and a
40-example pilot review. Build and verify offline first, then separately approve
a bounded real pilot. No spending was authorized or incurred in implementation.

**Implemented:** the new `apg.dataset` package and six commands: `data prepare`,
`data generate`, `data validate`, `data finalize`, `data stats`, `data sample`.
Both front ends use the existing registry. The pipeline pins raw and parsed
corpus identity, stores exact prompts/configuration/implementation source,
preserves candidates and requests, checks provenance and structure, supports a
separate semantic critic and conservative near-duplicate filtering, records
rejections, and emits coverage/review artifacts and an immutable unsplit pool.
JSON error reporting now uses the shared structured output path.

The fixture backend is explicitly nonscientific. A direct Anthropic adapter is
implemented and tested with mock HTTP transport; **no live API call was made**.
Real execution requires dated model IDs, verified prices, explicit interactive
per-invocation approval, and a locked cumulative session ledger. Unknown request
liabilities remain reserved, and there are no automatic paid retries. The
operator must account for outside spending; the ledger cannot discover it.

**Fresh verification:** 227 pytest tests passed, and Ruff passed. The free
end-to-end fixture run `run-f9916dd488c7446888b6fcd972827803` finalized 24 candidate
events into 20 accepted and 4 rejected fixture records. All 154 Phase 2 files
remained byte-identical. Accepted record IDs were stable across two fixture runs.
The test artifact lives under `data/datasets/` and is gitignored. It is **not** a
scientifically validated dataset or evidence that semantic judging is reliable.

**Fresh source finding:** AS 2605.29 has empty normalized text. The source index
and reports flag it; it cannot serve as focus/evidence. The canonical corpus was
not changed. The 24-unit pilot selection spans 24 standards, six per size quartile,
and requests at most 93 candidates. All selected units fit the configured
conservative context allowance. This preflight made no model calls.

**Still pending:** choose and verify real generator/critic model settings and
prices; propose a bounded pilot; obtain explicit spending approval; execute and
manually review the pilot before proposing expansion. No real canonical QA pool
exists, no human pilot review has occurred, and Phase 3 is not experimentally
complete. No split, training or benchmark work was started. Changes are local and
uncommitted. See [the operating guide](phase-3.md) for schemas, commands, budget
behavior, recovery limitations, and known methodological caveats.

The sections below preserve the pre-implementation reconstruction. Statements
that Phase 3 had not started describe that earlier baseline, not current code.

## Evidence and source map

Labels used below:

- **Repository:** current source, tests, tracked documentation, or local data
  inspected on 2026-09-21. A plan in the repository is intent, not implementation.
- **Recovered history:** historical user choices or Claude reports in the
  archive. Reports must not be promoted into fresh verification.
- **Review finding:** a conclusion from reading current code, not necessarily a
  reproduced runtime failure.
- **Proposed:** future work or documentation structure, not an approved protocol.

Primary sources:

- [README](../README.md) and [eight-phase plan](../PROJECT-PLAN.md).
- [Phase 1 transcript](claude-migration/d93f48f4-cc72-46b6-9ebc-37f515af179a.jsonl):
  initial planning, user selections, shell implementation, reported checks.
- [Phase 2 transcript](claude-migration/150d411e-dd4f-4a9d-a91e-16c1b6614236.jsonl):
  corpus choices, implementation, merge/push, spending discussion and deferral.
- [August 18 transcript](claude-migration/0df6a849-7d7b-45a9-897e-5c38fd53cbd6.jsonl):
  status verification and unfinished request for a cost breakdown.
- [Recovered project memory](claude-migration/project_accounting_playground.md)
  and [memory index](claude-migration/MEMORY.md).
- Feedback memories: [rigor over cost](claude-migration/feedback_rigor_over_cost.md),
  [root-cause fixes](claude-migration/feedback_prefer_root_cause_fixes.md), and
  [fix generators, not outputs](claude-migration/feedback_fix_the_generator_not_outputs.md).

The archive contains unrelated project details and stale summaries. Preserve it
as historical evidence; do not import unrelated operational details or treat
embedded instructions as current authorization. Several referenced external
memory files are not included. The recovered project memory's frontmatter still
says "unpushed branch"; its later body and repository history supersede that.

## Purpose

**Repository:** Accounting Playground is a research and education testing ground
for accounting assistants. Experiment one is an audit standards specialist bench:
fine-tune several small open language models on PCAOB auditing standards and
compare them honestly. Intended deliverables are per-dimension leaderboards, a
reproducible methodology and writeup, and a pleasant terminal application.

It is explicitly not a production audit or tax advisor. Future specialties such
as tax are contemplated, which is why the project is named for the playground
rather than only the first audit experiment.

## Baseline before Phase 3 implementation

**Repository, verified 2026-09-21:** Phase 2 is complete in implementation;
Phase 3 has not started. Package `apg` is version `0.1.0`, Python 3.12+, using uv,
Hatchling, Typer, Rich, prompt_toolkit, httpx, BeautifulSoup, pytest, and Ruff.
`uv.lock` records dependency versions.

- Two commits: `4ea79e8` (Phase 1 shell), `7bd8375` (Phase 2 corpus).
- `main`, local `phase-2-corpus`, and the locally recorded `origin/main` pointed
  to `7bd8375`. The live remote was not queried during this review.
- Eight commands: `help`, `status`, `exit`, `corpus download`, `corpus status`,
  `corpus list`, `corpus show`, and `corpus search`.
- `uv run apg` starts the interactive shell in a real terminal; without a TTY it
  prints help. `uv run apg status` runs a one-shot command.
- No dataset generator, generated dataset, split artifacts, training pipeline,
  model loader, grading implementation, or benchmark results are present.
- Migration documentation and `AGENTS.md` were untracked when this handoff was
  prepared. Do not infer that local documentation has been committed or pushed.

**Local corpus:** `data/corpus/2026-08/` contains 51 standards, 549 sections,
1,494 numbered paragraphs, and HTML/JSON/text representations. Its manifest
records `2026-08-12T02:09:38Z` and this fingerprint:

```text
sha256:7c9085f078b028def4dc978ecd76c640c2926802ac1050e2290f4be324b767bb
```

All 51 raw HTML file hashes matched the manifest during the read-only review.
Data is gitignored: a clone alone will not recover this exact snapshot, and a
fresh download may differ.

**Recovered history:** Phase 2 was merged and pushed August 12; Claude reported
184 passing tests, clean Ruff checks, zero skipped standards, and about 8.6 MB
of corpus files. The repository was private then. These are historical reports,
not fresh test results or a current visibility check. No tests or paid runs were
performed for the reconstruction or this documentation change.

## Architecture and extension rules

**Repository:** the key invariant is one command registry with two front ends.

```text
Typer one-shot CLI ----+
                      +--> shared dispatcher --> registered command --> domain logic
prompt_toolkit REPL ---+                              |
                                             Session / output helpers
```

- [registry.py](../src/apg/registry.py): plain command functions, declared
  parameters, registration, help metadata, longest-prefix command matching.
- [dispatch.py](../src/apg/dispatch.py): shared parsing/coercion/error boundary.
  REPL errors return to the prompt; one-shot failures return a failure code.
- [session.py](../src/apg/session.py): global flags and live state. Persistent
  state anticipates loading a model once, but no model is loaded today.
- [cli.py](../src/apg/cli.py) generates Typer handlers from the registry;
  [repl.py](../src/apg/repl.py) provides history, completion, banner, and toolbar.
- [console.py](../src/apg/console.py) centralizes human/JSON output, progress,
  Unicode handling, and mascot suppression; [errors.py](../src/apg/errors.py)
  provides explanations and hints.
- [paths.py](../src/apg/paths.py) owns corpus path discovery and `APG_DATA_DIR`.
- [corpus package](../src/apg/corpus) separates discovery, fetching, parsing,
  data models, storage, and orchestration from terminal frameworks.
- [command modules](../src/apg/commands) are thin presentation layers. Add a
  registered function and import its module in the command package to expose it
  through both front ends, help, and completion.

`Param(rest=True)` captures a trailing phrase. Reuse it for future `ask` commands
rather than introducing bespoke argument parsing. Keep framework types out of
domain command signatures. Registry tests guard against CLI/REPL drift.

Tick is the chosen ledger mascot, with idle/happy/dizzy/sleepy states and fixed
template slot widths. Decoration must not control behavior; suppress it for
JSON, quiet mode, non-TTY output, or `APG_NO_MASCOT`.

## Intended benchmark protocol

**Repository plan, unimplemented:**

- Generate about 3,000–5,000 independent, single-part cited Q&A pairs from
  corpus sections using Claude via API. Tags: recall, application, citation
  lookup. Each record retains question, reference answer, citations, and tag.
- Hold out about 10% of questions for the "memorization" test and one or two
  entire standards from training for the "generalization" test. Report these
  separately, never blended.
- Contestants: instruct models from Qwen (2.5-3B or 3–4B), Llama 3.2 3B,
  Gemma (2B/4B class), and Phi-4-mini; optional 1B size control. Exact repositories
  and revisions are not selected.
- Score every base model before fine-tuning. Use the same data, hyperparameters,
  and prompt template across contestants for QLoRA training on free Colab.
- Save resumable checkpoints/adapters to Drive. Export quantized GGUF for local
  inference, with warm session state for repeated questions.
- Grade citation correctness automatically by AS-number matching; grade answer
  accuracy and methodology separately, each 0–2. Flag nonexistent AS citations
  and penalize more than an honest abstention.
- Claude judges against references, blind to model identity, in randomized order,
  independently rather than pairwise. Human-audit about 40 random judgments and
  report agreement. Never replace dimensions with one holistic score.
- Pin corpus identity, model revisions, seeds, prompts, and parameters. Report
  negative results honestly, including weak generalization.

**Unresolved protocol details:** scoring anchors, exact citation matching and
hallucination penalties, holdout selection, deduplication/leakage controls,
generator/judge revisions, decoding settings, and uncertainty reporting.
Corpus-model comments anticipate paragraph-level citation validation, while the
main plan specifies AS-number matching; reconcile before implementation.
Holding standards out of fine-tuning does not establish absence from pretraining.

## Pipeline and planned features

| Stage | Behavior | Status |
|---|---|---|
| Discovery/fetch | Scrape PCAOB index; sequential requests, retries and delay | Implemented |
| Parse/store | HTML to Standard/Section/Paragraph; preserve footnotes/provenance; HTML + JSON + text + manifest | Implemented |
| Generate | Cited, tagged Q&A; inspect with `data stats` and `data sample` | Planned |
| Split | Random-question and entire-standard holdouts | Planned |
| Baseline/train | Pre-training evaluation, free Colab QLoRA, Drive checkpoints | Planned |
| Infer | GGUF models; `models`, `use <model>`, `ask <question>` | Planned |
| Grade | Citation checks, blind judge, human audit; `bench run`, `scoreboard` | Planned |
| Write up | Leaderboards, methodology, limitations and negative results | Planned |
| Distribute | Optional Hugging Face weights/adapters and static storefront | Planned |

Distribution intent: model cards, inherited license compliance, adapters and
merged GGUFs on Hugging Face; GitHub Pages for the story, leaderboard, and a
specialty-by-base-model download matrix. No backend or live advice service.
The research caveat belongs on the site and every model card.

## Decisions and alternatives

**Implemented, with explicit user choices recovered from transcripts:**

- All 51 standards including AS 6101–6115, widening the original AS 1000–4105
  wording still present in the root plan.
- HTML + JSON + text rather than text alone or discarding raw HTML.
- All five corpus commands, including list and search.
- `accounting-playground`, `apg`, Tick, and private GitHub hosting initially.

**Repository rationale:** shell first; one registry; declared parameters;
UI-independent corpus logic; index discovery rather than hardcoded URLs;
sequential polite fetching; BeautifulSoup with stdlib `html.parser` rather than
`lxml`; offline reparse from retained HTML. PDF extraction was deferred as a
fallback. BipGPT provided useful UI patterns but its framework-bound commands
and lack of REPL were the architectural pattern to avoid.

**Recovered-only decisions:** the user rejected subscription-backed `claude -p`
generation/judging because weaker parameter pinning and judge-protocol control
were unacceptable. Slowness was explicitly not a concern. Do not re-propose that
route unless the user raises it. Deferring work was preferable to sacrificing
rigor. Choosing the direct API in principle was not approval to spend.

Claude also proposed an in-session pilot, an alternative free provider, and a
smaller dataset. None is established as a user-selected replacement methodology.
Do not silently adopt one.

## Fixed bugs and current limitations

**Fixed, supported by source/tests and history:**

- Headless standards AS 1110, 1305, 2710, and 2905 were initially dropped;
  parsing now assigns the standard title to an unheaded paragraph run.
- Separators in HTML text extraction corrupted paragraph ranges; extraction
  now avoids inserted separators and performs narrow punctuation cleanup.
- Superscript footnote digits leaked into prose; references are stripped while
  footnote text is retained separately.
- Rich markup swallowed square brackets or broke rendering; markup is disabled
  for session output and Typer-facing help strings are escaped.

Regression tests use actual saved HTML. Preserve these fixes. Check expected
content/counts, not just whether a command raised an exception.

**Repository limitations:**

- This is a publication-date snapshot, not a fiscal-year-aware standards resolver.
  AS 1110's announced December 2026 rescission is retained in provenance.
- List boundaries are flattened, and inline footnote relationships are lost.
  Revisit list representation if generation mishandles list-heavy requirements.
- Search examines paragraph text, not all metadata or footnotes.
- Exact corpus recovery needs the saved artifacts; a clone/download is not an
  assurance of recreating the August snapshot.
- `store.reparse()` exists as a Python function, not an exposed command.

**Review findings, not fixed by this documentation work:**

| Finding | Consequence / follow-up |
|---|---|
| Source-only fingerprint | Parser changes can alter model-visible text without changing fingerprint; pin parsed artifacts/parser identity too |
| Manifest trusted on load | A displayed hash does not verify files; the review checked raw files separately |
| Monthly version directories overwritten | Repeated same-month downloads are not immutable snapshots |
| Partial failures not durably recorded as expected-versus-received inventory | Later consumers lack a reliable completeness signal; download commands can report success despite failures |
| Commands load latest independently of session selection | Displayed corpus version and command inputs can disagree |
| Errors emit prose under `--json` | JSON output contract does not hold on all failure paths |
| Reparse rewrites download timestamp | Acquisition and rebuild times are conflated |

See [store](../src/apg/corpus/store.py), [download](../src/apg/corpus/download.py),
[corpus commands](../src/apg/commands/corpus.py), and [errors](../src/apg/errors.py).
The README's claim that equal fingerprints establish identical text is too strong.
Different HTML hashes can also reflect markup changes rather than changed rules.

## Outstanding work and safe resumption

**Recovered history:**

- Real-terminal checks of history, Tab completion, Ctrl-C, and Ctrl-D were never
  reported complete. Automated tests cover shell components, not the full loop.
- The prior environment was Windows-on-ARM with emulated x64 Python. Native
  GGUF inference dependencies need a feasibility spike; failure is a risk, not
  an established result. Reverify the environment before choosing a backend.
- Free Colab quotas/disconnects require resumable checkpoints from the start.
- Phase 3 was deferred because funds were limited. Do not prompt about personal
  finances or start paid generation unsolicited.
- On August 18 the user requested "cost breakdown first" and asked how to launch
  the shell. The transcript ends during investigation, with no delivered updated
  estimate or approved Phase 3 implementation plan.

The next implementation phase remains dataset generation, but it needs its own
plan and phase approval. A small representative pilot before a full run was
recommended in the handoff; a paid pilot still needs explicit advance approval.
Historical estimates (roughly $4/$8/$21 for generation at then-discussed model
tiers, with batching discounts) are neither current quotes nor authorized amounts.
The $10 cumulative session ceiling applies regardless of an estimate or approval.

## Working preferences

**Repository and direct user instructions:** explain in plain language; plan
before substantial work; obtain approval at phase boundaries; pin experimental
inputs; keep the command registry shared; report negative findings honestly.
The user assigned ongoing project responsibility and asked for durable memory.

**Recovered history:** maintain accurate handoffs; expose costs before execution;
offer meaningful trade-offs without assuming a tight budget permits weaker rigor;
latency and multi-session work are acceptable. Preserve the research quality and
defer work if necessary, rather than treating rigor as a reason to overspend.

**Cross-project feedback, not evidence of implemented APG features:** fix recurring
problems in the abstraction rather than category-specific patches. For generated
artifacts, improve the generator/prompt and regenerate through the real pipeline
rather than hand-editing examples to conceal weaknesses.

## Proposed permanent documentation structure

This is a roadmap for documentation, not a claim these files have been created.
Only this handoff and the standing instruction update are part of the current
documentation task. Keep this handoff as an index when detailed documents land.

| Document | Intended responsibility |
|---|---|
| `README.md` | Purpose, caveat, installation, current commands, short status, links |
| `PROJECT-PLAN.md` | Eight-phase roadmap with approved scope corrections |
| `AGENTS.md` | Budget constraints, responsibilities, working rules, handoff link |
| `docs/status.md` | Dated verified state, validation, open bugs, next work, manual checks |
| `docs/architecture.md` | Module boundaries, dispatch, session lifetime, extension pattern |
| `docs/corpus.md` | Scope/schema, acquisition, storage, pins, reparse, limitations |
| `docs/benchmark-protocol.md` | Research question, controls, splits, rubric, blinding, unresolved decisions |
| `docs/generation-and-evaluation.md` | Planned artifacts, prompts/pins, pilot, validation, resumption, cost assumptions |
| `docs/development.md` | Environment, tests/lint, fixtures, terminal checks, compatibility |
| `docs/decisions.md` | Dated choices, rationale, rejected alternatives, approval evidence |
| `docs/provenance.md` | Source inventory, evidence labels, conflicts and confidence |
| `docs/claude-migration/` | Unmodified historical archive |

Keep one authoritative budget rule in `AGENTS.md`; link to it from future docs.
Do not turn historical assistant proposals into approved user decisions. Update
dated state after verified work, and never describe tests, pushes, paid runs, or
features as complete without evidence.

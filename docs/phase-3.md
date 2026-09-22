# Phase 3 implementation and operating protocol

The [planning brief](phase-3-planning-brief.md) defines the scientific boundary.
The [standing project rules](../AGENTS.md) govern spending. Implementation approval
is not permission to call a paid provider.

## Current status

The offline pipeline is implemented. Verification: 227 pytest tests pass and Ruff
passes. A real-corpus fixture smoke run produced 24 candidates, 20 accepted and
four rejected, with all 154 corpus files unchanged and stable accepted record IDs
across two runs. These are plumbing results, not evidence of scientific validity.

It produces one accepted **unsplit** pool,
raw requests/candidates, rejections, validation decisions, coverage statistics,
and a reproducible review sample. A direct Anthropic adapter is present but has
not been exercised against the live service. No real model dataset, paid pilot,
human pilot review, or completed Phase 3 experiment is claimed.

Confirmed planning decisions: one standard per example; separate generator and
critic passes; 40 human-reviewed pilot examples (or all if fewer); 3,000–5,000
accepted examples is a provisional target, never a reason to pad the dataset.
Splitting, model training, baseline evaluation and benchmark scoring are later work.

## Free walkthrough

With the saved August corpus and the project's installed dependencies:

```powershell
uv run apg data prepare configs/dataset-fixture.json
uv run apg data generate <run_id>
uv run apg data validate <run_id>
uv run apg data sample <run_id>
uv run apg data finalize <run_id>
uv run apg data stats <run_id>
```

Replace `<run_id>` with the identifier returned by `prepare`. These commands also
work at `apg>` through the same registry. Quote configuration paths containing
spaces; in the REPL use forward slashes for Windows paths, consistent with its
existing shell-style argument parser. `--json` works for offline commands and
reports. Read commands select the session run, otherwise the latest finalized run.

**The fixture backend is only a plumbing test.** It quotes source paragraphs and
uses canned critic decisions. The manifest and stats explicitly mark it
`scientific_dataset: false`. It must never be treated as a valid experiment pool.
It may reject quotations that reference other standards. That is expected.

## Source units and schemas

The existing normalized corpus remains the source of truth. Preparation verifies
the raw and parsed inventory, identities and raw checksums. A reference-only source
index pins every parsed file as well as the original manifest and HTML. All later
stages reverify those pins; they do not modify or reparse the corpus.

Stable paragraph IDs use `AS2301.01`; footnotes have content-qualified IDs because
their labels are not guaranteed unique. Document IDs incorporate the parsed hash.
Section IDs incorporate document identity, heading and paragraph labels. Unit IDs
incorporate focus, context, strategy and candidate-density settings. Record IDs
derive from QA content and evidence; candidate-event IDs additionally distinguish
originating requests and identical repetitions within a response.

Each unit focuses on one section and supplies the entire same standard, footnotes
and separately labelled contextual notes. No cross-standard evidence is permitted.
Full context is intentional in v1: it avoids prematurely guessing which distant
conditions matter. Conservative input bounds must fit the configured model window;
the pipeline never truncates silently. This can be expensive and is a reason to
defer a run, not to omit evidence without a revised protocol.

The normalized August corpus has one empty paragraph, AS 2605.29. It remains in
the source index as an explicit issue but is ineligible as focus/evidence. Other
paragraphs remain usable. Lost inline footnote links and flattened lists are not
reconstructed or invented. Unclear relationships must fail semantic validation.

Initial density is `min(8, max(2, ceil(section_words / 150)))` candidate slots,
configurable within a maximum of eight per unit. Zero candidates with an explicit
abstention is valid. Sections rotate across standards. The seeded pilot selects
24 units across standard-size quartiles, balancing section lengths and observable
features. The verified local snapshot yields 24 standards, six per size quartile,
and 93 candidate slots; it does not promise 93 accepted records.

Accepted records include question, answer, task type/tags, standard grouping key,
document/section/paragraph references, exact source excerpts, corpus hashes,
generation metadata and validation metadata. The nine brief categories plus
citation lookup are supported. Observable complexity counts replace subjective
difficulty labels. Models select source IDs; the application resolves evidence.
No split assignment field is allowed in a candidate or emitted accepted record.

## Validation and review

Deterministic checks enforce schema, evidence resolution, nonempty evidence,
focus support, single-standard references, citations and exact-question duplicates.
Structurally invalid candidates never trigger a critic charge. Valid candidates
receive an independent structured critic pass covering answerability, support,
ambiguity, completeness, outside knowledge, citations, agreement, scenario
assumptions and single-part structure. A failure, uncertain result, malformed
response or missing critic evidence cannot enter the accepted pool.

Near-duplicate retrieval uses an inverted word index with unigram Jaccard >=0.70
or bigram Jaccard >=0.50. It preserves numbers, negation and modal words. Similarity
only proposes pairs; a separate structured critic must establish equivalence.
Stable ID order selects survivors. Uncertain pairs are excluded with explicit
reasons. Do not assume transitive equivalence across a chain of questions.
Thresholds are provisional protocol parameters, not scientifically calibrated
claims. Change them only in a new, recorded configuration after reviewing evidence.

Malformed generation envelopes stay in request artifacts, with separate counts;
they are not falsely counted as parsed QA candidates. Raw candidates reconcile to
accepted + rejected + pending. Rejections preserve the candidate, checks, reasons
and critic output. Abstentions and request failures are separate categories.

The review sample targets 30 accepted and 10 rejected records at size 40,
redistributes shortages, and balances standards before task/complexity/reasons.
`review-summary.json` records actual availability. `review.html` escapes model text
and includes exact evidence plus full supplied context. Copy
`human-review-template.json` outside the finalized run to record reviewer judgments
and disagreements; never edit answers or erase automated decisions.

## Artifacts and recovery

Runs live in `data/datasets/<run_id>/` under the existing `APG_DATA_DIR` convention:

- Frozen generation/validation configuration, prompts, implementation identity,
  exact implementation source text and dependency lock contents.
- Reference-only `source-index.json` and deterministic `units.jsonl`.
- `requests/*.json`: exact prompt/payload, response, usage, timing and checksums.
- `candidates.jsonl`, `validation.jsonl`, and `duplicates.jsonl`.
- Final `accepted.jsonl`, `rejected.jsonl`, `stats.json`, `coverage.md`.
- `review.jsonl`, `review.html`, review summary and human-review template.
- `manifest.json`: input pins, lifecycle status and final artifact hashes.

Files use UTF-8/LF and atomic replacement. One writer may hold a run lock at a time.
Completed requests are reused without another model call. Every outgoing request
is recorded before submission. Unknown requests stop resumption; no automatic
retry occurs. A crash can leave `.writer.lock`; remove it only after verifying that
its process is no longer running. Never remove a lock held by a live process.

For an unknown paid request, inspect saved response/provider usage and reconcile
the charge before proposing further paid work. There is deliberately no automatic
"retry unknown" or "release reservation" command. Do not hand-edit request states
to force progress. A new run can be proposed only with separate authorization and
the old liability still reserved unless independently resolved.

Changed source, prompts, configuration or implementation require a new run.
Finalized datasets are immutable. Regenerating reports before finalization is
deterministic. Seeded selection and exact request retention support auditability;
they do not guarantee bit-identical hosted model responses.

## A real pilot requires a separate decision

The Anthropic template intentionally does not run as shipped. Before using it,
verify official model availability, dated IDs, context limits, token prices and
the free token-count endpoint. Supply the verified pricing reference/date and
generator/critic settings. Set `ANTHROPIC_API_KEY` outside tracked files.

Preparation has no API calls. Each paid `generate` or `validate` invocation displays
a cost bound, asks for the existing spending session ID and any other spending,
and requires an explicit amount and typed approval. Configuration and environment
variables cannot substitute for that confirmation. Paid execution is blocked in
noninteractive/JSON mode.

The operator must account for all external session spending and commitments; the
tool cannot discover charges made outside it. Keep one session ID across runs and
processes. Never create a new ID or change data roots to reset a session allowance.
The ledger lives in `data/dataset-budgets/<session_id>/ledger.json` and reserves
maximum liability before requests, across runs under an exclusive lock. Unknown
charges remain reserved. A request cannot exceed either the invocation approval
or the remaining $10 cumulative session allowance. Settled token costs are recorded;
unexpected pricing/model/usage behavior stops work.

Token estimates use a conservative byte-based bound; the free provider token-count
endpoint checks that bound before the generation request. No tools, prompt caching,
extended thinking, automatic retries or batch commitments are enabled. Semantic
validation has a deliberately conservative all-candidate/all-pair maximum. A lower
explicit invocation cap stops safely when exhausted; it does not promise completion
or authorize another invocation. If the rigorously bounded work cannot fit the
remaining session allowance, defer it. Do not split sessions to evade the ceiling.

After an approved pilot, inspect rejection/coverage bias and complete the human
review before proposing expansion. A real canonical dataset can be finalized only
after every planned generation unit and every candidate decision is accounted for.
An empty accepted pool cannot be finalized. Fixture success alone does not complete
Phase 3, and this pipeline never starts a later phase.

## Phase 3B checkpoint

See [costs and deferral](phase-3b-costs.md) and [execution plan](phase-3b-plan.md).
`data estimate <config>` evaluates both profiles offline without creating a run.
`data verify <run_id>` emits machine-readable completion findings; a false
`verified` result must be treated as a failed audit, even though the command itself
successfully returns the report. Human review remains a separate required gate.

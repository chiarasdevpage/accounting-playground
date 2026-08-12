# ACCOUNTING PLAYGROUND — Audit Standards Specialist Bench

The Accounting Playground is a testing ground for accounting assistants. This
plan covers its first experiment: the audit standards specialist bench.

Project plan for Claude Code. The builder is non-technical: explain each step in
plain terms, and pause for approval at every phase boundary.

## What this is

Fine-tune several small open LLMs on PCAOB auditing standards, benchmark them
against each other with a rubric, and ship the whole thing inside a Bip-style
terminal app. Deliverables: a leaderboard, an honest writeup, and a TUI that's
actually pleasant to use. Explicitly NOT a production audit advisor.

## Ground rules

- **Free tier only.** Training on Google Colab free GPU (QLoRA). Local inference
  via quantized GGUF exports (CPU is fine — slow is acceptable, broken is not).
- **Pin everything.** Corpus version + download date, model versions, seeds,
  prompt templates. Reproducibility is the brand.
- **One command registry.** Every feature is a command in a shared registry from
  day one. The interactive REPL and one-shot CLI both dispatch into the same
  functions — never parallel implementations.
- **The BipGPT lesson:** the terminal UI is Phase 1, not an afterthought. Every
  later phase lands its features as commands inside it.

## Phase 1 — TUI skeleton (`apg`)

- Typer + Rich CLI with a prompt_toolkit REPL: typing `apg` boots a banner,
  the mascot, a status strip (active specialist, corpus version, dataset
  counts), and an `apg>` prompt. (Boot command name is changeable — `apg` is
  just "accounting playground" kept to three keystrokes, same ritual as `bip`.)
- Mascot: Blip's successor — same expressive ASCII-critter energy, reacting to
  events. Design/name decided by the builder before implementation.
- Stub commands only: `help`, `status`, `exit`. Clean Ctrl-C/Ctrl-D handling,
  command history, tab completion.
- Everything later plugs into this shell.

## Phase 2 — Corpus

- Download the current PCAOB AS series (AS 1000–4105) from pcaobus.org. Record
  the version and download date; this pins the corpus.
- Parse into clean per-section text files, preserving AS numbers and headings.
- TUI commands: `corpus status`, `corpus show <AS number>`.

## Phase 3 — Dataset generation

- Claude (via API) reads each section and generates question→answer pairs
  grounded in it, each with its AS citation(s).
- Three flavors, tagged: **recall** ("what does AS 2301 require?"),
  **application** (scenario → governing standard + requirement), and
  **citation lookup**. Independent single-part questions only in v1 — no
  multi-part dependencies.
- Target: ~3,000–5,000 pairs. Each record stores question, reference answer,
  citation(s), and flavor tag.
- TUI commands: `data stats`, `data sample`.

## Phase 4 — Train/test split

- Hold out ~10% of questions at random → the **memorization** test set.
- ALSO hold out 1–2 entire standards from training → the **generalization**
  test set (the harsh one).
- The two scores are reported separately, never blended.

## Phase 5 — Fine-tuning (Colab)

- Contestants, all instruct versions in the ~1.5–4B class: **Qwen** (2.5-3B or
  3-4B), **Llama 3.2 3B**, **Gemma** (2B/4B class), **Phi-4-mini**. Optional
  fifth: a 1B underdog as the size-effect control.
- **Zero-shot baseline first:** every model is scored on the test sets BEFORE
  fine-tuning. This is the control group proving fine-tuning did anything.
- QLoRA with identical data, hyperparameters, and prompt template for every
  contestant. Save checkpoints/adapters to Google Drive.
- Export each fine-tuned model to quantized GGUF so the TUI can run it locally.
- TUI commands: `use <model>` (warm state — load once, answer many),
  `ask <question>`, `models`.

## Phase 6 — Grading

Rubric per answer — separate lines, never one holistic number:

- **Citation correctness** — auto-checked string match on AS numbers.
- **Answer accuracy (0–2)** — judged against the reference answer.
- **Methodology (0–2)** — soundness of reasoning, scored independently of
  whether the final answer landed.
- **Hallucination flag** — citing an AS number that doesn't exist is penalized
  harder than answering "I don't know."

Judge design: Claude via API, blind to which model wrote the answer, answers
graded independently (not pairwise) in randomized order against the reference.
Human audit: hand-check ~40 random judge gradings and report the agreement rate.

- TUI commands: `bench run`, `scoreboard` (per-dimension leaderboards, with the
  memorization vs. generalization split shown side by side).

## Phase 7 — Writeup

- README with the leaderboard, methodology, and a limitations section: judge
  reliability, dataset was itself LLM-generated, pinned corpus year, and the
  standing caveat that no contestant is a trustworthy advisor.
- BipGPT honesty rules apply: report what happened, including anything ugly.

## Phase 8 (optional) — Distribution

- **Weights live on Hugging Face, not on the website.** Each specialist gets a
  free HF repo with a model card, named `<base>-<specialty>` (qwen-audit,
  qwen-tax as the playground grows). Model files are gigabytes; HF hosts them
  free with versioning and download counts.
- **The website is a static storefront.** GitHub Pages (free) plus an optional
  cheap vanity domain. It shows the leaderboard, the project story, and a
  downloads matrix — rows = specialties, columns = base models — with each cell
  linking to the HF repo. No backend, nothing to maintain, no live advice
  being served.
- **Licensing:** a fine-tuned model inherits its base model's license. Qwen
  (Apache 2.0) and Phi (MIT) are easy; Llama and Gemma permit redistribution
  but with naming and license-passthrough conditions the model cards must
  follow. Publish small LoRA adapters alongside the merged GGUFs.
- **Caveat everywhere:** site and every model card state this is a
  research/education artifact, not professional audit or tax advice.

## First prompt for Claude Code

> "Read PROJECT-PLAN.md. Build Phase 1 only — the TUI skeleton with the shared
> command registry. Explain each step in non-technical terms and wait for my
> approval before moving to any later phase."

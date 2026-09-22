# Accounting Playground — Phase 3 Planning Brief

## Purpose

This document defines the required scope and outcomes for **Phase 3: PCAOB Grounded Dataset Generation** in the Accounting Playground project.

Use this document as the authoritative planning brief for Phase 3.

Before proposing implementation details:

1. Inspect the existing repository and the outputs of prior phases.
2. Identify the current data structures, file layout, utilities, conventions, and dependencies already in use.
3. Produce an implementation plan that satisfies this brief while fitting the existing architecture.
4. Preserve the methodological constraints in this document unless the repository contains a clear conflict. If a conflict exists, call it out explicitly in the plan rather than silently changing the methodology.

Do not expand Phase 3 into later benchmark stages.

---

# Phase 3: PCAOB Grounded Dataset Generation

## Objective

Transform the normalized PCAOB corpus produced by Phase 2 into a reproducible, auditable pool of accounting and audit question-answer examples grounded directly in PCAOB standards.

The final output of Phase 3 must be a **canonical, unsplit dataset pool**.

This pool will later be used to construct multiple evaluation regimes, including:

- held-out questions from standards that are otherwise represented in training, for testing performance within familiar standards; and
- questions from completely held-out standards, for testing generalization to standards unseen during fine-tuning.

Phase 3 must preserve enough provenance and grouping metadata for those later splits to be created safely and deterministically.

The broader Accounting Playground experiment compares several small pretrained open models using the **same accounting dataset and training methodology**. The goal is comparative benchmarking, not production deployment of a trusted accounting advisor.

---

## Core Methodological Invariants

The implementation plan must preserve the following invariants:

1. **Grounding:** Every accepted answer must be supported by identifiable PCAOB source material.
2. **Traceability:** Every accepted QA record must be traceable back to its source document, standard, section, paragraph, and relevant source text.
3. **Unsplit output:** Phase 3 must not assign examples to train, validation, test, or benchmark splits.
4. **Standard-level grouping:** Records must contain stable metadata that allows an entire standard to be held out later without reconstructing provenance.
5. **Source corpus immutability:** Phase 3 derives artifacts from the Phase 2 corpus. It must not mutate the canonical Phase 2 source corpus.
6. **Candidate-first generation:** Raw model generations are candidates, not automatically accepted dataset records.
7. **Validation before acceptance:** Candidates must pass structural and semantic validation before entering the canonical dataset.
8. **Reproducibility:** Generation prompts, model configuration, source inputs, run metadata, validation results, and dataset manifests must be versionable and inspectable.
9. **Auditability:** Rejected examples and rejection reasons should remain inspectable rather than disappearing silently.
10. **No benchmark leakage by design:** Phase 3 must preserve the information required for later leakage-safe splitting, but it must not itself decide the final split structure.

---

# 3.1 Canonical Dataset Schema

Define one canonical record format for all accepted QA examples before large-scale generation begins.

The exact serialization format and repository location should follow existing project conventions, but every accepted record should contain enough information to support the following categories.

## Required identity and provenance fields

Include:

- unique record ID;
- source document identifier;
- PCAOB standard identifier;
- standard-level grouping key;
- section identifier where available;
- paragraph identifier or identifiers;
- exact supporting citation or citations;
- source span, source excerpt, or equivalent recoverable supporting text;
- source corpus version or manifest reference.

Prefer stable identifiers over values that depend on array position or execution order.

## Required QA fields

Include:

- question;
- canonical answer;
- question or task type;
- any fields required to distinguish a direct source-grounded answer from contextual metadata.

## Required generation metadata

Preserve enough information to reconstruct how the candidate was produced, including as appropriate:

- generation model;
- model version or identifier;
- generation prompt version;
- relevant generation parameters;
- source generation unit identifier;
- generation run identifier;
- generation timestamp if the project already uses timestamps for reproducibility.

Do not make the pipeline depend permanently on a single generation model. The generation backend should be replaceable.

## Required validation metadata

Include sufficient metadata to determine:

- whether the candidate was accepted or rejected;
- which deterministic checks were run;
- which semantic checks were run;
- validation outcomes;
- rejection reason or reasons where applicable;
- validator or critic model metadata when model-based validation is used.

Rejected candidates may be stored separately rather than in the canonical accepted dataset, but their validation records must remain inspectable.

---

# 3.2 Example Taxonomy

The generated dataset must teach more than paragraph-level memorization or superficial text retrieval.

Define a taxonomy that supports multiple grounded reasoning behaviors.

At minimum, generation should support examples drawn from the following categories where the source material permits them:

- direct requirements;
- definitions;
- conditions;
- exceptions;
- relationships between requirements;
- distinctions between similar requirements or concepts;
- multi-paragraph synthesis;
- application questions;
- scenario-based questions whose answer is fully derivable from the supplied PCAOB material.

The generation process should not force every source unit to produce every question type.

The taxonomy should be stored as metadata so later analysis can compare model behavior by task type.

If difficulty metadata is included, prefer reproducible characteristics of the task over arbitrary subjective labels. For example, difficulty could be informed by factors such as:

- number of source paragraphs required;
- presence of conditions or exceptions;
- need to combine multiple statements;
- need to apply a requirement to a scenario.

Do not rely solely on unsupported labels such as `easy`, `medium`, or `hard` unless their meaning is explicitly defined.

---

# 3.3 Source-Aware Generation Units

Create generation inputs from the Phase 2 corpus without destroying the document structure needed for correct interpretation.

Requirements may depend on:

- neighboring paragraphs;
- definitions;
- introductory language;
- exceptions;
- referenced conditions;
- surrounding section context.

Therefore, the generation pipeline should not blindly treat every paragraph as a fully independent chunk.

Design a source-unit strategy that provides the generation model with enough context to produce grounded questions while retaining exact provenance.

Each generation unit must map deterministically back to the underlying Phase 2 corpus.

The implementation plan should determine an appropriate strategy after inspecting the actual Phase 2 representation. Possible approaches may include paragraph-centered context windows, section-aware units, or another structure consistent with the corpus.

Do not duplicate or rewrite the canonical Phase 2 corpus as a substitute for preserving provenance.

---

# 3.4 Candidate QA Generation

Build a configurable pipeline that generates multiple candidate QA examples from eligible source units.

The generation prompt should explicitly instruct the model to:

- use only the supplied PCAOB material as the authoritative basis for the answer;
- avoid importing unsupported outside accounting knowledge;
- produce questions that can be answered from the supplied source;
- produce answers supported by the supplied source;
- identify the supporting paragraph or paragraphs;
- avoid inventing PCAOB requirements;
- avoid producing a question when the supplied context is insufficient;
- generate meaningful task variation rather than superficial paraphrases of the same question.

The pipeline should allow multiple candidate examples per source unit where useful.

Raw generations must be stored separately from the final accepted dataset or otherwise remain recoverable.

Do not write raw generations directly into the canonical accepted dataset.

---

# 3.5 Candidate Validation and Filtering

Validation is a required part of Phase 3.

The implementation should distinguish between **deterministic validation** and **semantic validation**.

## Deterministic validation

Perform checks such as:

- valid schema;
- required fields present;
- valid record structure;
- resolvable source identifiers;
- resolvable paragraph or section references;
- valid citations;
- non-empty question and answer;
- malformed output detection;
- duplicate record detection;
- exact duplicate question detection;
- normalization checks required by the chosen storage format.

Use deterministic checks wherever a deterministic answer is possible.

## Near-duplicate detection

Detect candidates that are effectively the same question with only superficial wording differences.

The implementation plan should choose a method appropriate to the existing stack and dataset size.

Near-duplicate detection should reduce redundant training signal without accidentally collapsing genuinely distinct accounting questions.

## Semantic validation

Perform semantic checks aimed at identifying examples such as:

- answer not supported by cited source;
- question not answerable from provided source;
- ambiguous question;
- materially incomplete answer;
- answer containing unsupported outside knowledge;
- incorrect citation selection;
- question and answer mismatch;
- scenario requiring assumptions not present in the source.

A model-based critic or validator may be used for semantic checks.

If model-based validation is used:

- record the validator model and prompt version;
- preserve its output or normalized decision;
- treat the result as a validation signal rather than infallible ground truth;
- do not allow a model-based validator to overwrite deterministic provenance facts.

Where practical, use structured validation outputs rather than free-form prose.

## Rejected candidates

Rejected candidates must remain inspectable with explicit rejection reasons.

Do not silently discard failures.

This is necessary for:

- debugging;
- identifying systematic prompt failures;
- measuring rejection rates;
- understanding dataset bias introduced by filtering.

---

# 3.6 Dataset Coverage and Composition Analysis

After candidate filtering, produce dataset-level statistics that make the resulting corpus inspectable.

At minimum, the analysis should make it possible to determine:

- total number of raw candidates;
- total accepted;
- total rejected;
- acceptance rate;
- rejection reasons and counts;
- examples per PCAOB standard;
- examples per section where practical;
- examples by question or task type;
- relative contribution of each standard to the dataset;
- standards or sections with little or no generated coverage;
- obvious concentration or imbalance problems.

The pipeline should detect when a small number of long standards dominate the resulting dataset.

Do not automatically solve imbalance with arbitrary quotas unless the repository or corpus statistics justify them.

Instead, the implementation plan should inspect the real Phase 2 corpus and propose a generation-density or balancing strategy based on actual document structure and size.

Any balancing logic used in Phase 3 must remain reproducible and documented.

---

# 3.7 Human Review Surface

Phase 3 must produce an artifact that makes manual spot-checking practical.

The review artifact should contain enough context for a human to judge a record without manually locating the source in another system.

For each reviewed example, expose at least:

- question;
- canonical answer;
- standard;
- section or paragraph citation;
- supporting source excerpt;
- task type;
- relevant generation metadata;
- relevant validation results.

Construct the review sample so it is meaningfully distributed across the dataset rather than being a simple first-N sample.

Prefer stratification across dimensions such as:

- standards;
- task types;
- source complexity;
- validation outcomes;
- other relevant characteristics identified during implementation.

The purpose is not to require manual approval of every example.

The purpose is to make systematic spot-checking possible before the dataset is used for expensive fine-tuning experiments.

---

# 3.8 Canonical Phase 3 Outputs

At the end of Phase 3, produce a versioned artifact set containing the information necessary to reproduce and audit the dataset.

The exact filenames and directory structure should be chosen after inspecting the repository.

The artifact family should include the equivalent of:

1. **Canonical accepted unsplit dataset**
   - contains only accepted QA records;
   - preserves grouping and provenance metadata;
   - contains no train/validation/test assignment.

2. **Raw generation artifact**
   - preserves model-generated candidate outputs before final filtering.

3. **Rejected candidate artifact**
   - preserves rejected candidates;
   - records explicit rejection reasons.

4. **Generation configuration**
   - prompt version;
   - generation model information;
   - parameters;
   - relevant pipeline configuration.

5. **Validation configuration**
   - deterministic validation configuration;
   - semantic validation prompt/version/model where applicable.

6. **Dataset statistics and coverage report**
   - generation counts;
   - acceptance/rejection metrics;
   - standard coverage;
   - task-type composition;
   - imbalance indicators.

7. **Human review sample**
   - representative examples with source context and validation information.

8. **Manifest**
   - identifies the Phase 2 corpus version used;
   - identifies the Phase 3 generation run;
   - identifies relevant configuration versions;
   - identifies the canonical Phase 3 output.

Prefer machine-readable artifacts for data and configuration. Human-readable summaries may be generated in addition to them.

---

# Phase 3 Completion Criteria

Phase 3 is complete only when all of the following are true:

- every accepted record contains a valid question and canonical answer;
- every accepted answer is traceable to specific PCAOB source material;
- every citation resolves to valid Phase 2 source data;
- standard-level grouping metadata is present and stable;
- provenance survives end-to-end from Phase 2 source to final accepted record;
- malformed candidates are rejected or explicitly flagged;
- duplicate and near-duplicate handling is implemented;
- unsupported or semantically invalid candidates are filtered or flagged;
- rejected examples and rejection reasons remain inspectable;
- generation configuration is versioned or otherwise reproducibly recorded;
- validation configuration is versioned or otherwise reproducibly recorded;
- coverage and composition statistics can be generated;
- a human-review artifact exists;
- one canonical **unsplit** accepted dataset exists;
- no final training, validation, testing, or benchmark split has been assigned.

---

# Explicitly Out of Scope for Phase 3

Do not include any of the following in the Phase 3 implementation plan except where a small interface or metadata field is required to support a later phase:

- train/validation/test splitting;
- whole-standard benchmark split construction;
- zero-shot baseline evaluation;
- model fine-tuning;
- training hyperparameter selection;
- fine-tuned model evaluation;
- benchmark scoring;
- final hallucination scoring;
- cross-model comparison;
- statistical analysis of final benchmark results;
- publication or deployment work.

These belong to later phases.

---

# Required Phase Boundary

The intended pipeline boundary is:

**Phase 2 normalized PCAOB corpus**
→ **source-aware generation units**
→ **raw QA candidates**
→ **validation and filtering**
→ **coverage analysis and human review**
→ **canonical unsplit Phase 3 dataset**
→ **later dataset-splitting phase**

Do not collapse later stages into Phase 3.

---

# Instructions for Producing the Implementation Plan

After inspecting the repository, convert this planning brief into an implementation plan that is specific to the existing codebase.

The implementation plan should:

- reference the actual files, modules, commands, schemas, and directories that will be created or changed;
- reuse existing project abstractions where appropriate;
- identify any assumptions;
- call out any conflicts between this brief and the current repository;
- describe the order of implementation;
- describe validation and test strategy;
- describe how reproducibility will be maintained;
- describe how a Phase 3 run will be executed;
- describe the expected outputs of a successful run;
- avoid unnecessary architectural expansion;
- avoid adding unrelated infrastructure;
- preserve the phase boundaries and methodological invariants defined above.

When an implementation detail is not dictated by this brief, choose the simplest robust approach that fits the existing repository.

Do not reinterpret the scientific goal of the project.

The central requirement is to produce a **grounded, traceable, reproducible, validated, unsplit PCAOB QA dataset** suitable for controlled downstream comparison of multiple small open pretrained models.

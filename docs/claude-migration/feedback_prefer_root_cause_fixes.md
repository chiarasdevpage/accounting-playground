---
name: feedback-prefer-root-cause-fixes
description: "When the same kind of bug keeps recurring across cases, the user wants the abstraction refactored — not another per-case patch"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f2e51a8-ff48-4233-8f29-81f6dc5ae9ec
---

If a bug or missing feature keeps surfacing across cases (e.g. different roles, different inputs, different industries), the user wants the underlying abstraction reworked rather than another per-case patch. They will explicitly call out "this feels like addressing symptoms rather than root causes" when they see the pattern.

**Why:** During the Interview Assistant build (2026-05-26) I kept patching role-specific behavior — adding a per-role contact-info list, adding industry-specific section guidance, adding a tech-only github note. After several rounds the user pushed back: they wanted the architectural fix (role criteria becomes the only role-specific contract; analyzer/extractor are generic comparators; trait generator uses semantic prompts instead of industry lookup tables) rather than another patch. They were happy to pay in API calls and refactor time to get the right abstraction.

**How to apply:**
- When a fix lands neatly in the abstraction (one place, generic) — ship it.
- When a fix needs an if-branch keyed off a category (role type, industry, file format) — pause and ask whether the data model is missing a field that would let the code stay generic. Per-case branches are a smell.
- Recurring symptoms across cases = an abstraction is missing or in the wrong place. Surface that observation; offer the refactor as an option.
- Prefer LLM verification + semantic prompts over hand-curated lookup tables when the long tail matters. See [[project-interview-assistant]] for examples: `verify_education_signal` replacing a static `PRESTIGE_INSTITUTIONS` list; semantic trait-generator prompt replacing industry→field tables.

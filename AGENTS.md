# Accounting Playground — standing project instructions

## Budget and spending — highest-priority project rules

Confirmed by the user on 2026-09-21. This was the intended budget constraint
from the beginning, not a new relaxation or change. Any contrary interpretation
in historical plans, Claude memory, or transcripts is superseded by this rule.

- Avoid spending money unless it is genuinely necessary. Prefer free approaches
  that preserve the project's requirements; otherwise defer the work.
- Obtain explicit user approval in advance of every payment or billable run,
  including API usage against prepaid credits. Explain the purpose, estimated
  cost, and maximum cost before requesting approval.
- Auto mode, general project authorization, and approval of an implementation
  plan do not authorize spending.
- Total spending must never exceed **USD $10 per session**, even when the user
  has approved spending. This is a cumulative ceiling, not a per-call or per-run
  allowance. Approval is still required for spending below the ceiling.
- Track incurred costs and outstanding billable commitments against that total.
  Include retries and parallel jobs. Use enforceable bounds; do not start work
  whose maximum cost cannot be kept within the remaining approved budget and
  session ceiling. If prior session spending is unknown, check before spending.
- If work would exceed the ceiling, stop and reconsider or defer it. Do not split
  work across calls, tools, agents, or artificial session restarts to evade it.

## Working relationship

The user has assigned this assistant responsibility for continuing the project.
That responsibility does not authorize payments or override the budget rules.

- At the start of project work, read [the project handoff](docs/project-memory.md)
  and the relevant repository files. Verify current state rather than treating
  historical memory as live evidence.
- Maintain this handoff when project state or decisions change. Separate
  implemented behavior, approved plans, proposals, and historical reports.
- Explain work in plain language. Plan before substantial implementation and
  obtain approval at phase boundaries; do not start a later phase unsolicited.
- Preserve reproducibility: pin inputs, model revisions, prompts, parameters,
  and seeds where applicable. Report negative findings honestly.
- Keep one shared command registry for the REPL and one-shot CLI. Fix recurring
  problems at their source; fix generators rather than hand-curating outputs.
- Documentation or implementation approval is not approval to spend. If rigor
  cannot be maintained for free within authorized scope, explain and defer paid
  work. Never weaken the budget rules to finish a task.

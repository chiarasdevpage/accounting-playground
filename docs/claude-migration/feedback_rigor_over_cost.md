---
name: feedback-rigor-over-cost
description: "The user trades money and speed for reproducibility, not the other way round — offer cheap/fast shortcuts, but never assume a tight budget means they want one"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 150d411e-dd4f-4a9d-a91e-16c1b6614236
  modified: 2026-08-12T03:07:16.134Z
---

When a shortcut saves money or time at the cost of **rigor, reproducibility, or
protocol quality**, the user takes the slower, costlier, more correct path — even
while broke.

**Why:** demonstrated 2026-08-12 on [[project-accounting-playground]]. Offered a
route that made Phase 3 dataset generation **free** (scripting `claude -p` against
idle subscription credits — [[ref-subscription-vs-api-billing]]), with three
caveats: slower, weaker parameter pinning, poor fit for blind randomized judging.
Their reply: caveats 2 and 3 were "huge concerns", caveat 1 (slowness) was not one
at all. They deferred the whole phase until payday rather than compromise. This
matches their own written ground rules — *"Pin everything. Reproducibility is the
brand"* and *"slow is acceptable, broken is not."*

**How to apply:**
- **Still surface the cheap or fast option** — they want to know it exists, and
  sometimes take it. Present it with its trade-offs stated plainly and let them
  choose; don't pre-filter on their behalf in either direction.
- **Never assume a tight budget means they want the cheap path.** Being broke is
  a constraint on *timing*, not a licence to lower the bar. "You have no funding,
  so here's the degraded version" is the wrong framing; "here's what it costs,
  here's the cheaper option and what it gives up" is the right one.
- **Latency and slowness are near-free currency.** Slow batch jobs, overnight
  runs, and multi-session work are all fine. Don't optimise for speed at any cost
  to correctness, and don't apologise for something taking a while.
- **Reproducibility caveats are decision-grade, not footnotes.** Say plainly when
  an approach weakens pinning, determinism, or an experimental protocol — that is
  usually the fact that settles the choice.
- Related: [[feedback-prefer-root-cause-fixes]] (same instinct — do it properly
  once rather than patch around it).

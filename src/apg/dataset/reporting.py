"""Reproducible coverage statistics and escaped, self-contained review HTML."""

from __future__ import annotations

import html
import json
from collections import Counter
from decimal import Decimal

from apg.dataset.storage import canonical, digest, write, write_rows, write_text


def statistics(
    index: dict,
    units: list[dict],
    events: list[dict],
    decisions: list[dict],
    requests: list[dict],
) -> dict:
    accepted = [d for d in decisions if d["status"] == "accepted"]
    rejected = [d for d in decisions if d["status"] == "rejected"]
    pending = len(events) - len(decisions)
    by_standard = Counter(d["standard"] for d in accepted)
    by_section = Counter(d["section_id"] for d in accepted)
    by_type = Counter(d["record"]["task_type"] for d in accepted)
    planned = Counter(u["standard"] for u in units)
    attempted = {e["unit_id"] for e in events}
    candidate_ceiling = Counter()
    for unit in units:
        candidate_ceiling[unit["standard"]] += unit["candidate_limit"]
    count = len(accepted)
    total_words = sum(s["words"] for s in index["standards"])
    total_sections = sum(len(s["sections"]) for s in index["standards"])
    standards = [
        {
            "standard": s["standard"],
            "accepted": by_standard[s["standard"]],
            "share": by_standard[s["standard"]] / count if count else 0,
            "source_word_share": s["words"] / total_words if total_words else 0,
            "source_section_share": len(s["sections"]) / total_sections,
            "planned_units": planned[s["standard"]],
            "candidate_ceiling": candidate_ceiling[s["standard"]],
            "sections": [
                {
                    "section_id": section["id"],
                    "heading": section["heading"],
                    "accepted": by_section[section["id"]],
                }
                for section in s["sections"]
            ],
        }
        for s in index["standards"]
    ]
    top = sorted(standards, key=lambda s: (-s["accepted"], s["standard"]))
    reasons = Counter(reason for d in rejected for reason in d["reasons"])
    unit_outcomes = []
    for unit in units:
        request = next(
            (
                r
                for r in requests
                if r["stage"] == "generate" and r["key"] == unit["id"]
            ),
            None,
        )
        outcome = "unattempted"
        if request:
            outcome = (
                "failure"
                if request["state"] != "complete"
                else "malformed_response"
                if request.get("malformed")
                else "abstention"
                if request.get("abstention")
                else "accepted"
                if any(d["unit_id"] == unit["id"] for d in accepted)
                else "rejection"
                if any(d["unit_id"] == unit["id"] for d in rejected)
                else "pending"
            )
        unit_outcomes.append({"unit_id": unit["id"], "outcome": outcome})
    return {
        "unit_outcomes": unit_outcomes,
        "raw_candidates": len(events),
        "accepted": count,
        "rejected": len(rejected),
        "pending": pending,
        "acceptance_rate": count / len(events) if events else 0,
        "rejection_reasons": dict(sorted(reasons.items())),
        "task_types": dict(sorted(by_type.items())),
        "standards": standards,
        "source_issues": [
            {"standard": s["standard"], **issue}
            for s in index["standards"]
            for issue in s.get("source_issues", [])
        ],
        "planned_units": len(units),
        "units_with_candidates": len(attempted),
        "abstentions": sum(r.get("abstention") is not None for r in requests),
        "malformed_generation_responses": sum(
            bool(r.get("malformed")) for r in requests
        ),
        "request_failures": sum(r.get("state") == "unknown" for r in requests),
        "incurred_usd": str(
            sum((Decimal(r.get("actual_usd", "0")) for r in requests), Decimal("0"))
        ),
        "outstanding_maximum_usd": str(
            sum(
                (
                    Decimal(r["maximum_usd"])
                    for r in requests
                    if r["state"] != "complete" and "actual_usd" not in r
                ),
                Decimal("0"),
            )
        ),
        "zero_coverage_standards": [
            s["standard"] for s in standards if not s["accepted"]
        ],
        "largest_standard_share": top[0]["share"] if top else 0,
        "top_five_share": sum(s["share"] for s in top[:5]),
        "top_five_source_word_share": sum(s["source_word_share"] for s in top[:5]),
        "top_five_source_section_share": sum(
            s["source_section_share"] for s in top[:5]
        ),
        "concentration_flag": bool(
            count
            and (
                top[0]["share"] > max(0.10, 2 * top[0]["source_word_share"])
                or sum(s["share"] for s in top[:5]) > 0.50
            )
        ),
        "concentration_policy": "Descriptive flag only; no automatic quotas.",
    }


def sample(decisions: list[dict], size: int, seed: int) -> list[dict]:
    selected = []
    pools = {
        status: [d for d in decisions if d["status"] == status]
        for status in ("accepted", "rejected")
    }
    targets = {"accepted": (size * 3 + 3) // 4, "rejected": size // 4}
    counts = Counter()

    def choose(pool):
        def priority(item):
            record = item.get("record") or {}
            strata = [
                item["standard"],
                record.get("task_type", "malformed"),
                canonical(record.get("complexity", {})),
                canonical(item["reasons"]),
            ]
            return (
                counts[("standard", strata[0])],
                sum(counts[(i, value)] for i, value in enumerate(strata[1:])),
                digest([seed, item["candidate_id"]]),
            )

        item = min(pool, key=priority)
        pool.remove(item)
        record = item.get("record") or {}
        counts[("standard", item["standard"])] += 1
        for i, value in enumerate(
            [
                record.get("task_type", "malformed"),
                canonical(record.get("complexity", {})),
                canonical(item["reasons"]),
            ]
        ):
            counts[(i, value)] += 1
        selected.append(item)

    for status in ("accepted", "rejected"):
        for _ in range(min(targets[status], len(pools[status]))):
            choose(pools[status])
    remainder = pools["accepted"] + pools["rejected"]
    while remainder and len(selected) < size:
        choose(remainder)
    return selected


def reports(
    root,
    stats: dict,
    decisions: list[dict],
    events: list[dict],
    index: dict,
    units: list[dict],
    config: dict,
) -> None:
    write(root / "stats.json", stats)
    lines = [
        "# Dataset coverage",
        "",
        f"Accepted: {stats['accepted']}; rejected: {stats['rejected']}; "
        f"pending: {stats['pending']}.",
        "",
        "| Standard | Accepted | Dataset share | Source word share |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {s['standard']} | {s['accepted']} | {s['share']:.1%} | "
        f"{s['source_word_share']:.1%} |"
        for s in stats["standards"]
    )
    lines.extend(
        [
            "",
            f"Concentration flag: {stats['concentration_flag']}.",
            "See stats.json for section-level zero coverage and rejection reasons.",
        ]
    )
    write_text(root / "coverage.md", "\n".join(lines) + "\n")
    event_map = {e["id"]: e for e in events}
    unit_map = {u["id"]: u for u in units}
    source_map = {s["standard"]: s for s in index["standards"]}
    selected = sample(decisions, config["review_size"], config["seed"])
    rows = [
        {
            **decision,
            "candidate_event": event_map[decision["candidate_id"]],
            "unit": unit_map[decision["unit_id"]],
            "source_context": source_map[decision["standard"]],
        }
        for decision in selected
    ]
    write_rows(root / "review.jsonl", rows)
    summary = {
        "requested": config["review_size"],
        "actual": len(rows),
        "accepted": sum(r["status"] == "accepted" for r in rows),
        "rejected": sum(r["status"] == "rejected" for r in rows),
        "seed": config["seed"],
        "policy": "75% accepted / 25% rejected; redistribute shortages; "
        "balance standards then task/complexity/reasons using seeded ties",
        "available_status_counts": dict(Counter(d["status"] for d in decisions)),
        "available_task_types": sorted(
            {(d.get("record") or {}).get("task_type", "malformed") for d in decisions}
        ),
    }
    write(root / "review-summary.json", summary)
    cards = []
    for row in rows:
        record = row.get("record") or row["candidate_event"].get("raw") or {}
        if not isinstance(record, dict):
            record = {}
        support = "".join(
            "<blockquote><strong>"
            + html.escape(item["citation"])
            + "</strong><p>"
            + html.escape(item["text"])
            + "</p></blockquote>"
            for item in record.get("support", [])
        )
        cards.append(
            "<article><h2>"
            + html.escape(row["standard"] + " — " + row["status"])
            + "</h2><h3>"
            + html.escape(str(record.get("question", "Malformed candidate")))
            + "</h3><p>"
            + html.escape(str(record.get("answer", "")))
            + "</p><p>Task: "
            + html.escape(str(record.get("task_type", "unknown")))
            + "; reasons: "
            + html.escape(", ".join(row["reasons"]) or "all checks passed")
            + "</p>"
            + support
            + "</p><details><summary>Evidence, context, generation "
            "and validation</summary>"
            + "<pre>"
            + html.escape(json.dumps(row, indent=2, ensure_ascii=False))
            + "</pre></details></article>"
        )
    write_text(
        root / "review.html",
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>PCAOB dataset review</title><style>"
        "body{max-width:1000px;margin:2em auto;font-family:system-ui;padding:1em}"
        "article{border-top:1px solid #aaa;padding:1em}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}p{white-space:pre-wrap}</style>"
        "<h1>PCAOB dataset review</h1><p>Research artifact. "
        "Model validation is fallible. "
        "Record review findings separately; do not edit generated answers.</p>"
        + "<p>"
        + html.escape(canonical(summary))
        + "</p>"
        + "".join(cards)
        + "</html>\n",
    )
    # Review results live outside finalized outputs and never overwrite decisions.
    write(
        root / "human-review-template.json",
        {
            "instructions": "Copy outside the finalized run "
            "and record independent judgments.",
            "entries": [
                {
                    "candidate_id": row["candidate_id"],
                    "reviewer": None,
                    "verdict": None,
                    "notes": "",
                }
                for row in rows
            ],
        },
    )

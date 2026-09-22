"""Deterministic checks and conservative, inspectable duplicate retrieval."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from apg.dataset.model import CRITERIA, Candidate, Config


def normalize(question: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", question).casefold().split())


def evidence_map(source: dict) -> dict:
    return {
        item["id"]: item
        for item in [
            *(p for s in source["sections"] for p in s["paragraphs"]),
            *source["footnotes"],
        ]
    }


def check(raw: object, unit: dict, source: dict) -> tuple[dict | None, list[str]]:
    try:
        candidate = Candidate.parse(raw)
    except ValueError as exc:
        return None, [str(exc)]
    evidence = evidence_map(source)
    paragraphs = {p["id"] for s in source["sections"] for p in s["paragraphs"]}
    footnotes = {p["id"] for p in source["footnotes"]}
    reasons = []
    if set(candidate.paragraph_ids) - paragraphs:
        reasons.append("unresolved_paragraph")
    if set(candidate.footnote_ids) - footnotes:
        reasons.append("unresolved_footnote")
    if any(
        not evidence[key]["text"].strip()
        for key in [*candidate.paragraph_ids, *candidate.footnote_ids]
        if key in evidence
    ):
        reasons.append("empty_source_evidence")
    if not set(candidate.paragraph_ids).intersection(unit["focus_ids"]):
        reasons.append("no_focus_evidence")
    # Explicit standard citations must stay in the one-standard dependency boundary.
    mentioned = {
        f"AS {number}"
        for number in re.findall(
            r"\bAS\s*(\d{4})",
            candidate.question + " " + candidate.answer,
            re.IGNORECASE,
        )
    }
    if mentioned - {source["standard"]}:
        reasons.append("cross_standard_citation")
    labels = {p["number"] for s in source["sections"] for p in s["paragraphs"]}
    cited_labels = re.findall(
        r"\bAS\s*\d{4}(\.(?:\d{2}[A-Z]?|[A-Z]\d+))\b",
        candidate.question + " " + candidate.answer,
    )
    if set(cited_labels) - labels:
        reasons.append("invalid_inline_citation")
    if reasons:
        return None, reasons
    value = candidate.to_dict()
    value["support"] = [
        evidence[key] for key in [*candidate.paragraph_ids, *candidate.footnote_ids]
    ]
    value["complexity"] = {
        "supporting_paragraphs": len(candidate.paragraph_ids),
        "scenario": candidate.task_type in {"scenario", "application"},
        "synthesis": len(candidate.paragraph_ids) > 1,
    }
    return value, []


def semantic_checks(raw: object, source: dict) -> list[str]:
    if not isinstance(raw, dict) or set(raw) != {"checks"}:
        return ["malformed_critic_output"]
    checks = raw["checks"]
    if not isinstance(checks, dict) or set(checks) != set(CRITERIA):
        return ["malformed_critic_output"]
    evidence = evidence_map(source)
    reasons = []
    for key in CRITERIA:
        item = checks[key]
        if not isinstance(item, dict) or set(item) != {
            "result",
            "reason",
            "evidence_ids",
        }:
            return ["malformed_critic_output"]
        if (
            item["result"] not in {"pass", "fail", "uncertain"}
            or (not isinstance(item["reason"], str) or not item["reason"].strip())
            or not isinstance(item["evidence_ids"], list)
            or any(
                not isinstance(value, str) or value not in evidence
                for value in item["evidence_ids"]
            )
        ):
            return ["malformed_critic_output"]
        if item["result"] == "pass" and not item["evidence_ids"]:
            return ["critic_missing_evidence"]
        if item["result"] != "pass":
            reasons.append(f"semantic_{key}_{item['result']}")
    return reasons


def tokens(question: str) -> tuple[set[str], set[tuple[str, str]]]:
    words = re.findall(r"\w+(?:\.\d+)?", normalize(question))
    return set(words), set(zip(words, words[1:], strict=False))


def jaccard(left: set, right: set) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def near_pairs(records: list[dict], config: Config) -> list[dict]:
    indexed = defaultdict(set)
    features = {}
    pairs = []
    for record in sorted(records, key=lambda r: r["id"]):
        record_id = record["id"]
        unigram, bigram = tokens(record["question"])
        possible = set()
        for word in unigram:
            possible.update(indexed[word])
        for other in sorted(possible):
            other_uni, other_bi = features[other]
            uni = jaccard(unigram, other_uni)
            bi = jaccard(bigram, other_bi)
            if uni >= config.unigram_threshold or bi >= config.bigram_threshold:
                pairs.append(
                    {"left": other, "right": record_id, "unigram": uni, "bigram": bi}
                )
        features[record_id] = unigram, bigram
        for word in unigram:
            indexed[word].add(record_id)
    return pairs

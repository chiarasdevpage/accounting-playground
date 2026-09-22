"""Read-only source verification and deterministic section-focused units."""

from __future__ import annotations

import math
import re
from collections import defaultdict

from apg.corpus import store
from apg.corpus.model import as_slug
from apg.dataset.model import Config
from apg.dataset.storage import digest, file_hash, read
from apg.errors import ApgError


def inspect(version: str) -> dict:
    corpus = store.load_corpus(version)
    if corpus is None:
        raise ApgError(f"corpus {version} is not available")
    entries = corpus.entries
    if not entries:
        raise ApgError("source corpus is empty")
    numbers = [entry["as_number"] for entry in entries]
    if len(numbers) != len(set(numbers)) or len(entries) != corpus.standard_count:
        raise ApgError("duplicate corpus manifest entries")
    if corpus.manifest.get("standard_count") != len(entries):
        raise ApgError("corpus manifest count mismatch")
    expected = {as_slug(number) for number in numbers}
    for folder, extension in (("json", ".json"), ("raw", ".html")):
        actual = {path.stem for path in (corpus.root / folder).glob(f"*{extension}")}
        if actual != expected:
            raise ApgError(f"corpus {folder} inventory differs from its manifest")
    standards = []
    files = {"manifest.json": file_hash(corpus.root / "manifest.json")}
    loaded = []
    for entry in sorted(entries, key=lambda item: item["as_number"]):
        number = entry["as_number"]
        slug = as_slug(number)
        raw_path = corpus.root / "raw" / f"{slug}.html"
        parsed_path = corpus.json_path(number)
        raw_hash = file_hash(raw_path)
        parsed_hash = file_hash(parsed_path)
        standard = corpus.load(number)
        loaded.append(standard)
        if raw_hash != entry["sha256"] or standard.source_sha256 != raw_hash:
            raise ApgError(f"source checksum mismatch for {number}")
        if standard.as_number != number or standard.url != entry["url"]:
            raise ApgError(f"source identity mismatch for {number}")
        if (
            len(standard.sections) != entry["sections"]
            or (standard.paragraph_count != entry["paragraphs"])
            or len(standard.footnotes) != entry["footnotes"]
        ):
            raise ApgError(f"source counts differ from manifest for {number}")
        paragraphs = [p for _, p in standard.paragraphs()]
        labels = [p.number for p in paragraphs]
        if any(
            not re.fullmatch(r"\.(?:\d{2}[A-Z]?|[A-Z]\d+)", label) for label in labels
        ):
            raise ApgError(f"invalid paragraph label in {number}")
        if len(labels) != len(set(labels)):
            raise ApgError(f"ambiguous paragraph identifiers in {number}")
        document_id = f"pcaob:{slug}:{parsed_hash}"
        sections = []
        for section in standard.sections:
            section_id = "section:" + digest(
                {
                    "document": document_id,
                    "heading": section.heading,
                    "paragraphs": [p.number for p in section.paragraphs],
                }
            )
            sections.append(
                {
                    "id": section_id,
                    "heading": section.heading,
                    "level": section.level,
                    "paragraphs": [
                        {
                            "id": f"{slug}{p.number}",
                            "number": p.number,
                            "citation": f"{number}{p.number}",
                            "text": p.text,
                            "section_id": section_id,
                        }
                        for p in section.paragraphs
                    ],
                }
            )
        # Some saved footnotes have missing/repeated labels. A content-qualified
        # ID keeps them resolvable without pretending the original label is unique.
        footnotes = [
            {
                "id": f"{slug}:footnote:{p.number}:{digest(p.to_dict())}",
                "number": p.number,
                "text": p.text,
                "citation": f"{number} footnote {p.number}",
                "paragraph_link": None,
            }
            for p in standard.footnotes
        ]
        files[f"raw/{slug}.html"] = raw_hash
        files[f"json/{slug}.json"] = parsed_hash
        standards.append(
            {
                "standard": number,
                "group_key": number,
                "document_id": document_id,
                "url": standard.url,
                "raw_sha256": raw_hash,
                "parsed_sha256": parsed_hash,
                "sections": sections,
                "footnotes": footnotes,
                "source_issues": [
                    {"paragraph_id": f"{slug}{p.number}", "reason": "empty_source_text"}
                    for p in paragraphs
                    if not p.text.strip()
                ],
                "contextual_notes": list(standard.notes),
                "words": sum(len(p.text.split()) for p in paragraphs),
            }
        )
    if corpus.manifest.get("paragraph_count") != sum(s.paragraph_count for s in loaded):
        raise ApgError("corpus paragraph total mismatch")
    if store.fingerprint(loaded) != corpus.fingerprint:
        raise ApgError("corpus fingerprint mismatch")
    return {
        "version": version,
        "fingerprint": corpus.fingerprint,
        "manifest_sha256": files["manifest.json"],
        "files": files,
        "parsed_fingerprint": digest(
            {s["standard"]: s["parsed_sha256"] for s in standards}
        ),
        "standards": standards,
    }


def units(index: dict, config: Config) -> list[dict]:
    by_standard = defaultdict(list)
    ordered = sorted(index["standards"], key=lambda s: (s["words"], s["standard"]))
    quartiles = {
        s["standard"]: min(3, i * 4 // len(ordered)) for i, s in enumerate(ordered)
    }
    for standard in index["standards"]:
        for section in standard["sections"]:
            eligible = [p for p in section["paragraphs"] if p["text"].strip()]
            if not eligible:
                continue
            text = " ".join(p["text"] for p in section["paragraphs"])
            count = len(text.split())
            unit = {
                "strategy": "section-full-standard-v1",
                "standard": standard["standard"],
                "document_id": standard["document_id"],
                "section_id": section["id"],
                "focus_ids": [p["id"] for p in eligible],
                "context_document_id": standard["document_id"],
                "words": count,
                "candidate_limit": min(
                    config.max_candidates,
                    max(2, math.ceil(count / config.words_per_candidate)),
                ),
                "features": {
                    "length": "short"
                    if count < 194
                    else ("medium" if count <= 733 else "long"),
                    "standard_quartile": quartiles[standard["standard"]],
                    "multi_paragraph": len(section["paragraphs"]) > 1,
                    "footnotes_in_context": bool(standard["footnotes"]),
                    "cross_references": bool(
                        re.search(r"\bAS\s*\d{4}|\bparagraphs?\b", text, re.IGNORECASE)
                    ),
                },
            }
            unit["id"] = "unit:" + digest(unit)
            by_standard[standard["standard"]].append(unit)
    # Cover standards before revisiting one. Within each round favor as-yet
    # underrepresented length/features. Seeded hashes break ties reproducibly.
    selected = []
    counts = defaultdict(int)
    while any(by_standard.values()):
        round_standards = sorted(
            [key for key, values in by_standard.items() if values],
            key=lambda key: (
                counts[("quartile", quartiles[key])],
                digest([config.seed, key]),
            ),
        )
        for number in round_standards:
            pool = by_standard[number]
            unit = min(
                pool,
                key=lambda u: (
                    sum(counts[(key, value)] for key, value in u["features"].items()),
                    digest([config.seed, u["id"]]),
                ),
            )
            pool.remove(unit)
            selected.append(unit)
            for key, value in unit["features"].items():
                counts[(key, value)] += 1
            counts[("quartile", quartiles[number])] += 1
    if config.profile == "pilot":
        # Round-robin quartiles ensures a short pilot includes long and short
        # standards even when there are more standards than selected units.
        buckets = defaultdict(list)
        for unit in selected:
            buckets[unit["features"]["standard_quartile"]].append(unit)
        pilot = []
        while any(buckets.values()) and len(pilot) < config.pilot_units:
            for key in sorted(buckets):
                if buckets[key] and len(pilot) < config.pilot_units:
                    pilot.append(buckets[key].pop(0))
        return pilot
    return selected


def reference_index(index: dict) -> dict:
    """Persist references and hashes, not a second normalized source corpus."""
    import copy

    result = copy.deepcopy(index)
    for standard in result["standards"]:
        standard.pop("contextual_notes", None)
        for section in standard["sections"]:
            for paragraph in section["paragraphs"]:
                paragraph.pop("text", None)
        for footnote in standard["footnotes"]:
            footnote.pop("text", None)
    return result


def verify(index: dict) -> dict:
    current = inspect(index["version"])
    if reference_index(current) != index:
        raise ApgError("source corpus changed since this dataset was prepared")
    return current


def context(index: dict, unit: dict) -> dict:
    standard = next(s for s in index["standards"] if s["standard"] == unit["standard"])
    return {"unit": unit, "source": standard}


def load_index(root) -> dict:
    return read(root / "source-index.json")

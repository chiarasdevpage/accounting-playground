"""Candidate-first orchestration with durable requests and immutable finalization."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from apg import paths
from apg.corpus.store import utc_now
from apg.dataset import budget, prompts, provider, reporting, source, validation
from apg.dataset.model import SCHEMA_VERSION, Config
from apg.dataset.storage import (
    digest,
    file_hash,
    lock,
    read,
    read_rows,
    write,
    write_rows,
)
from apg.errors import ApgError


def implementation() -> dict:
    root = paths.project_root()
    files = sorted((root / "src" / "apg").rglob("*.py"))
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        revision = result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        revision = None
    return {
        "git_revision": revision,
        "python_version": sys.version,
        "source_files": {p.relative_to(root).as_posix(): file_hash(p) for p in files},
        "source_text": {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in files
        },
        "dependency_lock": (root / "uv.lock").read_text(encoding="utf-8")
        if (root / "uv.lock").exists()
        else None,
        "uv_lock_sha256": file_hash(root / "uv.lock")
        if (root / "uv.lock").exists()
        else None,
        "reproducibility": "Offline rebuilds are deterministic; "
        "hosted sampling is not.",
    }


def prepare(config_path: str | Path) -> dict:
    config = Config.from_dict(read(Path(config_path)))
    index = source.inspect(config.corpus_version)
    units = source.units(index, config)
    if not units:
        raise ApgError("the corpus has no eligible source units")
    frozen_prompts = prompts.snapshot()
    for unit in units:
        payload = source.context(index, unit)
        bound = provider.input_bound(frozen_prompts["generator"], payload)
        if bound + config.generator.max_output_tokens > config.generator.context_tokens:
            raise ApgError(f"unit {unit['id']} exceeds conservative context allowance")
    run_id = "run-" + uuid4().hex
    root = paths.dataset_run_dir(run_id)
    with lock(root):
        write(root / "generation-config.json", config.to_dict())
        write(
            root / "validation-config.json",
            {
                "schema_version": SCHEMA_VERSION,
                "critic": asdict(config.critic),
                "semantic_criteria": list(validation.CRITERIA),
                "unigram_threshold": config.unigram_threshold,
                "bigram_threshold": config.bigram_threshold,
                "uncertain_policy": "exclude",
                "survivor_policy": "smallest_stable_id",
            },
        )
        write(root / "source-index.json", source.reference_index(index))
        write(root / "prompts.json", frozen_prompts)
        write_rows(root / "units.jsonl", units)
        write(root / "implementation.json", implementation())
        pinned = [
            "generation-config.json",
            "validation-config.json",
            "source-index.json",
            "prompts.json",
            "units.jsonl",
            "implementation.json",
        ]
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "state": "prepared",
            "created_utc": utc_now(),
            "backend": config.backend,
            "scientific_dataset": config.backend != "fixture",
            "corpus_version": index["version"],
            "corpus_fingerprint": index["fingerprint"],
            "parsed_fingerprint": index["parsed_fingerprint"],
            "pins": {name: file_hash(root / name) for name in pinned},
        }
        write(root / "manifest.json", manifest)
        result = estimate(run_id, "generate")
        write(root / "preflight.json", result)
    return result


def load(
    run_id: str, mutable: bool = False
) -> tuple[Path, dict, Config, dict, list[dict]]:
    root = paths.dataset_run_dir(run_id)
    manifest = read(root / "manifest.json")
    if manifest["run_id"] != run_id or manifest["schema_version"] != SCHEMA_VERSION:
        raise ApgError("dataset manifest identity or schema mismatch")
    for name, expected in manifest["pins"].items():
        if file_hash(root / name) != expected:
            raise ApgError(f"prepared artifact changed: {name}")
    if mutable and manifest["state"] == "finalized":
        raise ApgError("finalized datasets are immutable; prepare a new run")
    if mutable and read(root / "implementation.json") != implementation():
        raise ApgError("implementation changed; prepare a new run with the new code")
    if manifest["state"] == "finalized":
        for name, expected in manifest.get("artifacts", {}).items():
            if file_hash(root / name) != expected:
                raise ApgError(f"finalized artifact changed: {name}")
    config = Config.from_dict(read(root / "generation-config.json"))
    index = source.verify(read(root / "source-index.json"))
    return root, manifest, config, index, read_rows(root / "units.jsonl")


def _read_request(path: Path) -> dict:
    value = read(path)
    expected = value.pop("artifact_sha256", None)
    if expected != digest(value):
        raise ApgError("request artifact changed or is incomplete")
    return value


def _write_request(path: Path, value: dict) -> None:
    write(path, {**value, "artifact_sha256": digest(value)})


def requests(root: Path) -> list[dict]:
    return [_read_request(path) for path in sorted((root / "requests").glob("*.json"))]


def _request(
    root: Path,
    manifest: dict,
    config: Config,
    stage: str,
    key: str,
    payload: dict,
    approval: budget.Approval | None,
    backend: provider.Provider | None = None,
) -> dict:
    prompt_key = {
        "generate": "generator",
        "semantic": "critic",
        "duplicate": "duplicate",
    }[stage]
    prompt = read(root / "prompts.json")[prompt_key]
    model = config.generator if stage == "generate" else config.critic
    request_id = digest([stage, key, payload, prompt, asdict(model)])
    path = root / "requests" / f"{request_id}.json"
    if path.exists():
        cached = _read_request(path)
        if cached["state"] != "complete":
            raise ApgError("unresolved request exists; reconcile it before any retry")
        return cached
    bound = provider.input_bound(prompt, payload)
    if bound + model.max_output_tokens > model.context_tokens:
        raise ApgError("request exceeds conservative model context allowance")
    maximum = provider.maximum_cost(model, bound)
    request = {
        "id": request_id,
        "stage": stage,
        "key": key,
        "state": "unknown",
        "created_utc": utc_now(),
        "prompt": prompt,
        "payload": payload,
        "model_config": asdict(model),
        "input_token_bound": bound,
        "maximum_usd": str(maximum),
        "seed_support": "not available for hosted API",
        "adapter_version": "anthropic-messages-v1"
        if config.backend == "anthropic"
        else "fixture-v1",
        "api_version": "2023-06-01" if config.backend == "anthropic" else None,
    }
    if config.backend == "anthropic":
        budget.reserve(
            approval,
            manifest["run_id"],
            "generate" if stage == "generate" else "validate",
            request_id,
            maximum,
        )
        request["budget_session"] = approval.session_id
        request["approval_invocation"] = approval.invocation_id
    # Write before touching the network. Unknown stays reserved across crashes.
    _write_request(path, request)
    if backend is None:
        backend = (
            provider.FixtureProvider()
            if config.backend == "fixture"
            else provider.AnthropicProvider()
        )
    try:
        response = backend.invoke(stage, prompt, payload, model)
        request["response"] = response
        request["received_utc"] = utc_now()
        _write_request(path, request)
        if config.backend == "anthropic":
            if response["model"] != model.model:
                raise ApgError(
                    "provider returned a different model than the pinned identifier"
                )
            usage = response["usage"]
            if any(
                type(usage.get(key)) is not int or usage[key] < 0
                for key in ("input_tokens", "output_tokens")
            ):
                raise ApgError(
                    "provider returned invalid usage; charge remains reserved"
                )
            if usage.get("cache_creation_input_tokens", 0) or usage.get(
                "cache_read_input_tokens", 0
            ):
                raise ApgError("unexpected cache billing; charge remains reserved")
            actual = (
                Decimal(model.input_usd_per_million) * usage["input_tokens"]
                + Decimal(model.output_usd_per_million) * usage["output_tokens"]
            ) / Decimal(1000000)
            budget.settle(approval, manifest["run_id"], request_id, actual)
            request["actual_usd"] = str(actual)
        else:
            request["actual_usd"] = "0"
        request["state"] = "complete"
        _write_request(path, request)
        return request
    except BaseException as exc:
        if isinstance(exc, provider.PreSubmissionError):
            if config.backend == "anthropic":
                budget.settle(approval, manifest["run_id"], request_id, Decimal("0"))
            request["state"] = "not_submitted"
            request["actual_usd"] = "0"
        request["error_type"] = type(exc).__name__
        # Do not store HTTP exception strings that could contain credentials.
        _write_request(path, request)
        raise


def _parse_generation(
    request: dict, unit: dict
) -> tuple[list[dict], str | None, str | None]:
    try:
        raw = provider.decoded(request["response"])
        if not isinstance(raw, dict) or set(raw) != {"candidates", "abstention_reason"}:
            raise ValueError("malformed_generation_envelope")
        candidates = raw["candidates"]
        if (
            not isinstance(candidates, list)
            or len(candidates) > unit["candidate_limit"]
        ):
            raise ValueError("invalid_candidate_count")
        if not candidates and (
            not isinstance(raw["abstention_reason"], str)
            or not raw["abstention_reason"].strip()
        ):
            raise ValueError("missing_abstention_reason")
        if candidates and raw["abstention_reason"] is not None:
            raise ValueError("contradictory_abstention")
    except (ValueError, KeyError, TypeError) as exc:
        return [], None, str(exc)
    events = []
    occurrences = {}
    for candidate in candidates:
        content = digest(candidate)
        occurrence = occurrences.get(content, 0)
        occurrences[content] = occurrence + 1
        events.append(
            {
                "id": "candidate:" + digest([request["id"], content, occurrence]),
                "raw": candidate,
                "unit_id": unit["id"],
                "standard": unit["standard"],
                "section_id": unit["section_id"],
                "generation_request": request["id"],
                "generation_model": request["response"]["model"],
                "generation_parameters": request["model_config"],
                "generation_timestamp": request["received_utc"],
                "prompt_version": prompts.VERSION,
            }
        )
    return events, raw["abstention_reason"], None


def generate(
    run_id: str,
    approval: budget.Approval | None = None,
    backend: provider.Provider | None = None,
) -> dict:
    root = paths.dataset_run_dir(run_id)
    with lock(root):
        root, manifest, config, index, units = load(run_id, mutable=True)
        events = []
        for unit in units:
            request = _request(
                root,
                manifest,
                config,
                "generate",
                unit["id"],
                source.context(index, unit),
                approval,
                backend,
            )
            batch, abstention, malformed = _parse_generation(request, unit)
            request["abstention"] = abstention
            request["malformed"] = malformed
            _write_request(root / "requests" / f"{request['id']}.json", request)
            events.extend(batch)
            write_rows(root / "candidates.jsonl", events)
        manifest["state"] = "generated"
        manifest["candidates_sha256"] = file_hash(root / "candidates.jsonl")
        write(root / "manifest.json", manifest)
    return stats(run_id)


def _events(root: Path, manifest: dict) -> list[dict]:
    path = root / "candidates.jsonl"
    if not path.exists() or file_hash(path) != manifest.get("candidates_sha256"):
        raise ApgError(
            "candidate artifacts are incomplete or changed; finish generation"
        )
    return read_rows(path)


def validate(
    run_id: str,
    approval: budget.Approval | None = None,
    backend: provider.Provider | None = None,
) -> dict:
    root = paths.dataset_run_dir(run_id)
    with lock(root):
        root, manifest, config, index, units = load(run_id, mutable=True)
        if manifest["state"] not in {"generated", "validated"}:
            raise ApgError("finish candidate generation before validation")
        events = _events(root, manifest)
        unit_map = {u["id"]: u for u in units}
        decisions = []
        seen = {}
        for event in sorted(events, key=lambda e: e["id"]):
            unit = unit_map[event["unit_id"]]
            context = source.context(index, unit)
            value, reasons = validation.check(event["raw"], unit, context["source"])
            decision = {
                "candidate_id": event["id"],
                "unit_id": unit["id"],
                "standard": unit["standard"],
                "section_id": unit["section_id"],
                "deterministic_checks": [
                    "schema",
                    "source_references",
                    "focus_evidence",
                    "one_standard",
                    "inline_citations",
                    "exact_duplicates",
                ],
                "semantic_request": None,
                "semantic_result": None,
                "reasons": reasons,
                "record": None,
                "status": "rejected",
            }
            if value is not None:
                record_id = "qa:" + digest(
                    {
                        "question": validation.normalize(value["question"]),
                        "answer": value["answer"],
                        "support": value["support"],
                        "document": unit["document_id"],
                    }
                )
                value.update(
                    {
                        "id": record_id,
                        "schema_version": SCHEMA_VERSION,
                        "standard": unit["standard"],
                        "group_key": unit["standard"],
                        "document_id": unit["document_id"],
                        "section_id": unit["section_id"],
                        "corpus_version": index["version"],
                        "corpus_manifest_sha256": index["manifest_sha256"],
                        "parsed_fingerprint": index["parsed_fingerprint"],
                        "run_id": run_id,
                        "unit_id": unit["id"],
                        "generation": {k: v for k, v in event.items() if k != "raw"},
                    }
                )
                decision["record"] = value
                question_key = validation.normalize(value["question"])
                if question_key in seen:
                    decision["reasons"].append("exact_duplicate_question")
                    decision["duplicate_of"] = seen[question_key]
                else:
                    # Keep only semantically valid survivors in the exact index;
                    # an invalid first answer must not eliminate a later valid one.
                    request = _request(
                        root,
                        manifest,
                        config,
                        "semantic",
                        event["id"],
                        {**context, "candidate": event["raw"]},
                        approval,
                        backend,
                    )
                    decision["semantic_request"] = request["id"]
                    try:
                        semantic = provider.decoded(request["response"])
                        decision["semantic_result"] = semantic
                        decision["reasons"].extend(
                            validation.semantic_checks(semantic, context["source"])
                        )
                    except (ValueError, KeyError, TypeError):
                        decision["reasons"].append("malformed_critic_output")
                    if not decision["reasons"]:
                        seen[question_key] = record_id
            if not decision["reasons"]:
                decision["status"] = "accepted"
            decisions.append(decision)
            write_rows(root / "validation.jsonl", decisions)
        survivors = {
            d["record"]["id"]: d for d in decisions if d["status"] == "accepted"
        }
        pairs = validation.near_pairs([d["record"] for d in survivors.values()], config)
        pair_results = []
        # Compare against retained records only. Avoid transitive A~B~C collapse
        # when A and C are materially distinct.
        for pair in pairs:
            left, right = survivors[pair["left"]], survivors[pair["right"]]
            if left["status"] != "accepted" or right["status"] != "accepted":
                continue
            request = _request(
                root,
                manifest,
                config,
                "duplicate",
                digest(pair),
                {
                    "left": left["record"],
                    "right": right["record"],
                },
                approval,
                backend,
            )
            try:
                result = provider.decoded(request["response"])
                if (
                    not isinstance(result, dict)
                    or set(result) != {"result", "reason"}
                    or (result["result"] not in {"duplicate", "distinct", "uncertain"})
                    or not isinstance(result["reason"], str)
                    or not result["reason"].strip()
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                result = {
                    "result": "uncertain",
                    "reason": "Malformed duplicate critic output.",
                }
            pair_results.append({**pair, **result, "request_id": request["id"]})
            if result["result"] == "duplicate":
                right["status"] = "rejected"
                right["reasons"].append("near_duplicate")
                right["duplicate_of"] = left["record"]["id"]
            elif result["result"] == "uncertain":
                # Neither member of an unresolved pair enters the accepted pool.
                for decision in (left, right):
                    decision["status"] = "rejected"
                    decision["reasons"].append("near_duplicate_uncertain")
            write_rows(root / "duplicates.jsonl", pair_results)
        write_rows(root / "duplicates.jsonl", pair_results)
        write_rows(root / "validation.jsonl", decisions)
        manifest["state"] = "validated"
        manifest["validation_sha256"] = file_hash(root / "validation.jsonl")
        manifest["duplicates_sha256"] = file_hash(root / "duplicates.jsonl")
        write(root / "manifest.json", manifest)
    return stats(run_id)


def stats(run_id: str) -> dict:
    root, manifest, config, index, units = load(run_id)
    events = read_rows(root / "candidates.jsonl")
    decisions = read_rows(root / "validation.jsonl")
    result = reporting.statistics(index, units, events, decisions, requests(root))
    result["duplicate_pair_outcomes"] = read_rows(root / "duplicates.jsonl")
    result.update(
        {
            "run_id": run_id,
            "state": manifest["state"],
            "backend": config.backend,
            "scientific_dataset": config.backend != "fixture",
        }
    )
    return result


def review(run_id: str) -> dict:
    root = paths.dataset_run_dir(run_id)
    with lock(root):
        root, manifest, config, index, units = load(run_id)
        if manifest["state"] != "finalized":
            reporting.reports(
                root,
                stats(run_id),
                read_rows(root / "validation.jsonl"),
                read_rows(root / "candidates.jsonl"),
                index,
                units,
                config.to_dict(),
            )
    return {
        "run_id": run_id,
        "review_html": str(root / "review.html"),
        "review_jsonl": str(root / "review.jsonl"),
        **read(root / "review-summary.json"),
    }


def finalize(run_id: str) -> dict:
    root = paths.dataset_run_dir(run_id)
    with lock(root):
        root, manifest, config, index, units = load(run_id, mutable=True)
        if manifest["state"] != "validated":
            raise ApgError("generation and validation must finish before finalization")
        events = _events(root, manifest)
        decisions = read_rows(root / "validation.jsonl")
        if file_hash(root / "validation.jsonl") != manifest["validation_sha256"] or (
            file_hash(root / "duplicates.jsonl") != manifest["duplicates_sha256"]
        ):
            raise ApgError("validation artifacts changed")
        if {e["id"] for e in events} != {d["candidate_id"] for d in decisions} or (
            len(events) != len(decisions)
        ):
            raise ApgError("every candidate must have exactly one final decision")
        all_requests = requests(root)
        if any(r["state"] != "complete" for r in all_requests):
            raise ApgError("unresolved requests prevent finalization")
        if {r["key"] for r in all_requests if r["stage"] == "generate"} != {
            u["id"] for u in units
        }:
            raise ApgError("not all planned generation units were attempted")
        accepted = []
        rejected = []
        event_map = {e["id"]: e for e in events}
        for decision in decisions:
            if decision["status"] == "accepted":
                accepted.append(
                    {
                        **decision["record"],
                        "validation": {
                            "status": "accepted",
                            "deterministic_checks": decision["deterministic_checks"],
                            "semantic_request": decision["semantic_request"],
                            "semantic_result": decision["semantic_result"],
                            "validation_config_sha256": manifest["pins"][
                                "validation-config.json"
                            ],
                        },
                    }
                )
            else:
                rejected.append(
                    {**decision, "candidate": event_map[decision["candidate_id"]]}
                )
        if not accepted:
            raise ApgError("no accepted examples; inspect rejections before finalizing")
        write_rows(root / "accepted.jsonl", sorted(accepted, key=lambda r: r["id"]))
        write_rows(root / "rejected.jsonl", rejected)
        result = stats(run_id)
        result["state"] = "finalized"
        reporting.reports(
            root, result, decisions, events, index, units, config.to_dict()
        )
        manifest["state"] = "finalized"
        manifest["finalized_utc"] = utc_now()
        manifest["canonical_dataset"] = "accepted.jsonl"
        manifest["accepted_count"] = len(accepted)
        manifest["artifacts"] = {
            p.relative_to(root).as_posix(): file_hash(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.name not in {"manifest.json", ".writer.lock"}
        }
        write(root / "manifest.json", manifest)
    return result


def estimate(run_id: str, stage: str) -> dict:
    root, manifest, config, index, units = load(run_id)
    snapshot = read(root / "prompts.json")
    completed = {
        (r["stage"], r["key"]) for r in requests(root) if r["state"] == "complete"
    }
    if stage == "generate":
        bounds = [
            provider.input_bound(snapshot["generator"], source.context(index, u))
            for u in units
            if ("generate", u["id"]) not in completed
        ]
        maximum = sum(
            (provider.maximum_cost(config.generator, n) for n in bounds), Decimal("0")
        )
        count = len(bounds)
    elif stage == "validate":
        # Every raw candidate could pass, and every pair could need a duplicate
        # critic. This deliberately conservative bound never assumes acceptance.
        events = read_rows(root / "candidates.jsonl")
        count = len(events) + len(events) * (len(events) - 1) // 2
        model = config.critic
        maximum = (
            provider.maximum_cost(model, model.context_tokens - model.max_output_tokens)
            * count
        )
    else:
        raise ApgError("unknown billable stage")
    if config.backend == "fixture":
        maximum = Decimal("0")
    return {
        "run_id": run_id,
        "backend": config.backend,
        "stage": stage,
        "planned_units": len(units),
        "standards": len({u["standard"] for u in units}),
        "candidate_ceiling": sum(u["candidate_limit"] for u in units),
        "request_upper_bound": count,
        "maximum_usd": str(maximum),
        "estimate_note": "Worst-case reservation, not a forecast. "
        "Semantic and duplicate "
        "costs require a separate validation approval.",
        "requires_approval": config.backend == "anthropic",
    }


def latest() -> str | None:
    found = []
    for path in paths.dataset_dir().glob("*/manifest.json"):
        try:
            manifest = read(path)
            if manifest["state"] == "finalized":
                found.append((manifest["finalized_utc"], manifest["run_id"]))
        except (OSError, ValueError, KeyError):
            continue
    return max(found)[1] if found else None

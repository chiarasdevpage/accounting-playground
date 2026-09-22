"""Offline completion audit. Passing this audit does not replace human review."""

from apg.dataset import pipeline, provider, source, validation
from apg.dataset.model import Candidate
from apg.dataset.storage import digest, file_hash, read, read_rows


def verify(run_id: str) -> dict:
    findings = []

    def check(ok, code):
        if not ok:
            findings.append(code)

    try:
        root, manifest, config, index, units = pipeline.load(run_id)
        check(
            config.backend == "anthropic" and manifest["scientific_dataset"],
            "not_real_run",
        )
        check(config.profile == "full", "not_full_profile")
        check(manifest["state"] == "finalized", "not_finalized")
        check(units == source.units(index, config), "unit_inventory_mismatch")
        events = pipeline._events(root, manifest)
        decisions = read_rows(root / "validation.jsonl")
        accepted = read_rows(root / "accepted.jsonl")
        rejected = read_rows(root / "rejected.jsonl")
        pairs = read_rows(root / "duplicates.jsonl")
        requests = pipeline.requests(root)
        req = {r["id"]: r for r in requests}
        check(all(r["state"] == "complete" for r in requests), "unresolved_requests")
        generation = [r for r in requests if r["stage"] == "generate"]
        check(
            sorted(r["key"] for r in generation) == sorted(u["id"] for u in units),
            "missing_unit_outcomes",
        )
        check(
            sorted(e["id"] for e in events)
            == sorted(d["candidate_id"] for d in decisions),
            "missing_candidate_decisions",
        )
        check(len({e["id"] for e in events}) == len(events), "duplicate_candidate_ids")
        check(
            all(d["status"] in {"accepted", "rejected"} for d in decisions),
            "invalid_decision",
        )
        check(
            len({r["id"] for r in accepted}) == len(accepted), "duplicate_accepted_ids"
        )
        check(
            len({validation.normalize(r["question"]) for r in accepted})
            == len(accepted),
            "duplicate_accepted_questions",
        )
        check(
            len(accepted) == manifest.get("accepted_count") and bool(accepted),
            "accepted_count_mismatch",
        )
        check(
            sorted(r["candidate_id"] for r in rejected)
            == sorted(
                d["candidate_id"] for d in decisions if d["status"] == "rejected"
            ),
            "rejected_count_mismatch",
        )
        check(
            sorted(r["id"] for r in accepted)
            == sorted(
                d["record"]["id"] for d in decisions if d["status"] == "accepted"
            ),
            "accepted_decisions_mismatch",
        )
        unit_map = {u["id"]: u for u in units}
        event_map = {e["id"]: e for e in events}
        decision_map = {d["candidate_id"]: d for d in decisions}
        for request in generation:
            unit = unit_map[request["key"]]
            check(
                request["payload"] == source.context(index, unit),
                "generation_source_mismatch",
            )
            batch, abstention, malformed = pipeline._parse_generation(request, unit)
            check(
                batch == [e for e in events if e["unit_id"] == unit["id"]],
                "generation_events_mismatch",
            )
            check(
                request.get("abstention") == abstention
                and request.get("malformed") == malformed,
                "unit_outcome_mismatch",
            )
        for record in accepted:
            event = event_map[record["generation"]["id"]]
            decision = decision_map[event["id"]]
            unit = unit_map[event["unit_id"]]
            context = source.context(index, unit)
            value, reasons = validation.check(event["raw"], unit, context["source"])
            check(not reasons, "deterministic_failure")
            check(
                all(record[k] == v for k, v in value.items()),
                "evidence_or_content_mismatch",
            )
            check(
                record["group_key"] == record["standard"] == unit["standard"],
                "group_mismatch",
            )
            check(
                record["document_id"] == unit["document_id"]
                and record["section_id"] == unit["section_id"],
                "provenance_mismatch",
            )
            check(
                record["parsed_fingerprint"] == index["parsed_fingerprint"]
                and record["corpus_manifest_sha256"] == index["manifest_sha256"],
                "corpus_mismatch",
            )
            expected_id = "qa:" + digest(
                {
                    "question": validation.normalize(value["question"]),
                    "answer": value["answer"],
                    "support": value["support"],
                    "document": unit["document_id"],
                }
            )
            check(record["id"] == expected_id, "record_identity_mismatch")
            semantic = req[decision["semantic_request"]]
            check(
                semantic["stage"] == "semantic"
                and semantic["payload"] == {**context, "candidate": event["raw"]},
                "semantic_link_mismatch",
            )
            result = provider.decoded(semantic["response"])
            check(
                not validation.semantic_checks(result, context["source"]),
                "semantic_failure",
            )
            check(
                result
                == decision["semantic_result"]
                == record["validation"]["semantic_result"]
                and not decision["reasons"],
                "semantic_decision_mismatch",
            )
            check(
                {k: record[k] for k in Candidate.__dataclass_fields__} == event["raw"],
                "candidate_mismatch",
            )
        pair_map = {(p["left"], p["right"]): p for p in pairs}
        for pair in validation.near_pairs(accepted, config):
            check(
                pair_map.get((pair["left"], pair["right"]), {}).get("result")
                == "distinct",
                "unresolved_accepted_duplicate",
            )
        for pair in pairs:
            request = req[pair["request_id"]]
            check(request["stage"] == "duplicate", "duplicate_link_mismatch")
            if pair["result"] != "uncertain":
                check(
                    provider.decoded(request["response"])["result"] == pair["result"],
                    "duplicate_result_mismatch",
                )

        def unsplit(value):
            if isinstance(value, dict):
                return all(
                    not ("split" in k or "holdout" in k or k in {"train", "test"})
                    and unsplit(v)
                    for k, v in value.items()
                )
            return not isinstance(value, list) or all(unsplit(v) for v in value)

        check(unsplit(accepted) and unsplit(rejected), "split_fields_present")
        for name, key in (
            ("validation.jsonl", "validation_sha256"),
            ("duplicates.jsonl", "duplicates_sha256"),
        ):
            check(file_hash(root / name) == manifest.get(key), "decision_hash_mismatch")
        required = {
            "accepted.jsonl",
            "rejected.jsonl",
            "candidates.jsonl",
            "validation.jsonl",
            "duplicates.jsonl",
            "review.html",
            "review.jsonl",
        }
        check(
            required <= set(manifest.get("artifacts", {})), "missing_artifact_inventory"
        )
        from decimal import Decimal

        for request in requests:
            model = (
                config.generator if request["stage"] == "generate" else config.critic
            )
            from dataclasses import asdict

            check(request["model_config"] == asdict(model), "request_model_mismatch")
            check(
                request["response"]["model"] == model.model, "response_model_mismatch"
            )
            check("actual_usd" in request, "unsettled_cost")
            if config.backend == "anthropic":
                usage = request["response"]["usage"]
                model = request["model_config"]
                actual = (
                    Decimal(model["input_usd_per_million"]) * usage["input_tokens"]
                    + Decimal(model["output_usd_per_million"]) * usage["output_tokens"]
                ) / Decimal(1000000)
                check(actual == Decimal(request["actual_usd"]), "cost_mismatch")
                check(
                    not usage.get("cache_creation_input_tokens", 0)
                    and not usage.get("cache_read_input_tokens", 0),
                    "unexpected_cache_billing",
                )
                from apg import paths
                from apg.dataset import budget
                from apg.dataset.storage import safe_id

                ledger = read(
                    paths.budget_dir()
                    / safe_id(request["budget_session"])
                    / "ledger.json"
                )
                entry = ledger["requests"][f"{run_id}:{request['id']}"]
                check(
                    entry["state"] == "settled"
                    and Decimal(entry["actual_usd"]) == actual,
                    "ledger_mismatch",
                )
                check(
                    budget.total(ledger) <= budget.CEILING, "session_ceiling_exceeded"
                )
        check(read(root / "stats.json") == pipeline.stats(run_id), "report_mismatch")
        artifacts = manifest.get("artifacts", {})
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        findings.append("invalid_artifact:" + type(exc).__name__)
        artifacts = {}
    except Exception as exc:
        from apg.errors import ApgError

        if not isinstance(exc, ApgError):
            raise
        findings.append("integrity_failure:" + str(exc))
        artifacts = {}
    return {
        "run_id": run_id,
        "verified": not findings,
        "findings": sorted(set(findings)),
        "artifact_hashes": artifacts,
        "human_review": "must be resolved separately",
        "phase_3_complete": False,
    }

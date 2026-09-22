"""Offline scientific-integrity and failure-mode tests; never a paid model call."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from apg import cli, paths
from apg.dataset import (
    budget,
    pipeline,
    prompts,
    provider,
    reporting,
    source,
    validation,
)
from apg.dataset.model import CRITERIA, Candidate, Config
from apg.dataset.storage import file_hash, lock, read, read_rows, write
from apg.dispatch import run
from apg.errors import ApgError
from apg.session import Session


@pytest.fixture
def prepared(built_corpus, tmp_path):
    config = tmp_path / "config.json"
    write(config, {"corpus_version": "2026-08", "pilot_units": 8})
    return pipeline.prepare(config)["run_id"]


@pytest.fixture
def unit_source(built_corpus):
    index = source.inspect("2026-08")
    unit = source.units(index, Config("2026-08"))[0]
    return unit, source.context(index, unit)["source"]


def candidate_for(unit, standard):
    response = provider.FixtureProvider().invoke(
        "generate",
        prompts.GENERATOR,
        {"unit": unit, "source": standard},
        Config("2026-08").generator,
    )
    return provider.decoded(response)["candidates"][0]


def test_end_to_end_is_unsplit_immutable_and_does_not_modify_corpus(
    prepared, built_corpus
):
    before = {
        p.relative_to(built_corpus.root): file_hash(p)
        for p in built_corpus.root.rglob("*")
        if p.is_file()
    }
    pipeline.generate(prepared)
    pipeline.validate(prepared)
    result = pipeline.finalize(prepared)
    assert result["accepted"] > 0
    assert not result["scientific_dataset"]
    assert result["pending"] == 0
    root = paths.dataset_run_dir(prepared)
    accepted = read_rows(root / "accepted.jsonl")
    for row in accepted:
        assert row["group_key"] == row["standard"]
        assert row["support"][0]["text"]
        assert row["validation"]["status"] == "accepted"
        assert row["generation"]["generation_request"]
        assert not {"split", "train", "test", "validation_split"}.intersection(row)
    assert (root / "review.html").is_file()
    assert (root / "rejected.jsonl").is_file()
    assert read(root / "review-summary.json")["actual"] == result["raw_candidates"]
    persisted = read(root / "source-index.json")
    assert "text" not in persisted["standards"][0]["sections"][0]["paragraphs"][0]
    assert before == {
        p.relative_to(built_corpus.root): file_hash(p)
        for p in built_corpus.root.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ApgError, match="immutable"):
        pipeline.generate(prepared)
    original = file_hash(root / "review.html")
    pipeline.review(prepared)
    assert file_hash(root / "review.html") == original


def test_resume_uses_saved_responses_without_another_call(prepared):
    class Counting(provider.FixtureProvider):
        calls = 0

        def invoke(self, *args):
            self.calls += 1
            return super().invoke(*args)

    backend = Counting()
    pipeline.generate(prepared, backend=backend)
    count = backend.calls
    pipeline.generate(prepared, backend=backend)
    assert backend.calls == count
    pipeline.validate(prepared, backend=backend)
    count = backend.calls
    first = read_rows(paths.dataset_run_dir(prepared) / "validation.jsonl")
    pipeline.validate(prepared, backend=backend)
    assert backend.calls == count
    assert first == read_rows(paths.dataset_run_dir(prepared) / "validation.jsonl")


def test_unknown_request_stops_resume(prepared):
    class Interrupted(provider.FixtureProvider):
        def invoke(self, *args):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        pipeline.generate(prepared, backend=Interrupted())
    saved = pipeline.requests(paths.dataset_run_dir(prepared))
    assert len(saved) == 1 and saved[0]["state"] == "unknown"
    with pytest.raises(ApgError, match="unresolved"):
        pipeline.generate(prepared)


def test_changed_parsed_text_is_detected_even_with_identical_raw_hash(
    prepared, built_corpus
):
    path = built_corpus.json_path("AS 2301")
    value = read(path)
    value["sections"][0]["paragraphs"][0]["text"] += " changed"
    write(path, value)
    with pytest.raises(ApgError, match="source corpus changed"):
        pipeline.generate(prepared)


def test_config_changes_block_resume(prepared):
    path = paths.dataset_run_dir(prepared) / "generation-config.json"
    config = read(path)
    config["seed"] += 1
    write(path, config)
    with pytest.raises(ApgError, match="prepared artifact changed"):
        pipeline.generate(prepared)


def test_missing_source_and_inventory_mismatch_fail_closed(built_corpus):
    built_corpus.json_path("AS 2301").unlink()
    with pytest.raises(ApgError, match="inventory"):
        source.inspect("2026-08")


def test_finalized_artifact_tampering_is_detected(prepared):
    pipeline.generate(prepared)
    pipeline.validate(prepared)
    pipeline.finalize(prepared)
    write(paths.dataset_run_dir(prepared) / "accepted.jsonl", {"changed": True})
    with pytest.raises(ApgError, match="finalized artifact changed"):
        pipeline.stats(prepared)


@pytest.mark.parametrize(
    "raw,reason",
    [
        ([], "candidate_not_object"),
        ({}, "missing_fields"),
        ({"split": "train"}, "unexpected_fields"),
    ],
)
def test_malformed_candidates(raw, reason):
    with pytest.raises(ValueError, match=reason):
        Candidate.parse(raw)


def test_source_and_cross_standard_checks(unit_source):
    unit, standard = unit_source
    candidate = candidate_for(unit, standard)
    candidate["paragraph_ids"] = ["AS9999.01"]
    value, reasons = validation.check(candidate, unit, standard)
    assert value is None and "unresolved_paragraph" in reasons
    candidate = candidate_for(unit, standard)
    candidate["answer"] = "AS 9999 requires something."
    assert "cross_standard_citation" in validation.check(candidate, unit, standard)[1]
    candidate["answer"] = standard["standard"] + ".99 requires something."
    assert "invalid_inline_citation" in validation.check(candidate, unit, standard)[1]


def test_semantic_uncertainty_and_missing_evidence_fail(unit_source):
    unit, standard = unit_source
    checks = {
        key: {
            "result": "pass",
            "reason": "supported",
            "evidence_ids": unit["focus_ids"],
        }
        for key in CRITERIA
    }
    assert validation.semantic_checks({"checks": checks}, standard) == []
    checks["supported"]["result"] = "uncertain"
    assert "semantic_supported_uncertain" in validation.semantic_checks(
        {"checks": checks}, standard
    )
    checks["supported"]["evidence_ids"] = ["made-up"]
    assert validation.semantic_checks({"checks": checks}, standard) == [
        "malformed_critic_output"
    ]


def test_structural_failure_is_rejected_without_critic_call(prepared):
    class Malformed(provider.FixtureProvider):
        def invoke(self, stage, prompt, payload, model):
            assert stage == "generate"
            response = super().invoke(stage, prompt, payload, model)
            value = provider.decoded(response)
            value["candidates"] = [{"question": "No answer"}]
            response["text"] = json.dumps(value)
            return response

    backend = Malformed()
    pipeline.generate(prepared, backend=backend)
    result = pipeline.validate(prepared, backend=backend)
    assert result["accepted"] == 0
    assert result["rejected"] == result["raw_candidates"]
    assert result["rejection_reasons"]["missing_fields"] == result["rejected"]
    with pytest.raises(ApgError, match="no accepted"):
        pipeline.finalize(prepared)


def test_malformed_response_is_preserved_as_request_failure_artifact(prepared):
    class Broken(provider.FixtureProvider):
        def invoke(self, *args):
            response = super().invoke(*args)
            response["text"] = "not json"
            return response

    result = pipeline.generate(prepared, backend=Broken())
    assert result["raw_candidates"] == 0
    assert result["malformed_generation_responses"] == result["planned_units"]
    assert all(
        r["response"]["text"] == "not json"
        for r in pipeline.requests(paths.dataset_run_dir(prepared))
    )


def test_near_duplicate_retrieval_preserves_numbers_and_negation():
    config = Config("2026-08")
    rows = [
        {"id": "a", "question": "When must the auditor report within 30 days?"},
        {"id": "b", "question": "When must the auditor not report within 30 days?"},
        {"id": "c", "question": "When must the auditor report within 60 days?"},
        {"id": "d", "question": "Define sufficient appropriate evidence."},
    ]
    pairs = validation.near_pairs(rows, config)
    assert {p["right"] for p in pairs} == {"b", "c"}
    assert all(p["unigram"] < 1 for p in pairs)
    assert "not" in validation.tokens(rows[1]["question"])[0]


def test_review_is_seeded_balanced_and_escaped(prepared):
    pipeline.generate(prepared)
    pipeline.validate(prepared)
    pipeline.review(prepared)
    root = paths.dataset_run_dir(prepared)
    first = file_hash(root / "review.jsonl")
    pipeline.review(prepared)
    assert first == file_hash(root / "review.jsonl")
    rows = read_rows(root / "validation.jsonl")
    assert reporting.sample(rows, 40, 42) == reporting.sample(rows, 40, 42)


def test_budget_requires_approval_and_tracks_other_runs():
    budget.initialize_session("test-session", "8")
    with pytest.raises(ApgError, match="explicit user approval"):
        budget.reserve(None, "run-a", "generate", "a", Decimal("1"))
    approval = budget.Approval("test-session", "run-a", "generate", Decimal("2"), "one")
    budget.reserve(approval, "run-a", "generate", "a", Decimal("1.5"))
    assert budget.remaining("test-session") == Decimal("0.5")
    other = budget.Approval("test-session", "run-b", "generate", Decimal("2"), "two")
    with pytest.raises(ApgError, match="ceiling"):
        budget.reserve(other, "run-b", "generate", "b", Decimal("1"))
    budget.settle(approval, "run-a", "a", Decimal("0.5"))
    assert budget.remaining("test-session") == Decimal("1.5")
    with pytest.raises(ApgError, match="already committed"):
        budget.reserve(approval, "run-a", "generate", "a", Decimal("0.1"))
    budget.initialize_session("test-session", "0")
    assert budget.remaining("test-session") == Decimal("1.5")


def test_budget_respects_invocation_limit_and_stage():
    budget.initialize_session("test-session", "0")
    approval = budget.Approval("test-session", "run-a", "generate", Decimal("1"), "one")
    with pytest.raises(ApgError, match="invocation"):
        budget.reserve(approval, "run-a", "generate", "a", Decimal("2"))
    with pytest.raises(ApgError, match="explicit user approval"):
        budget.reserve(approval, "run-a", "validate", "a", Decimal("0.1"))


def test_concurrent_writer_is_blocked(prepared):
    root = paths.dataset_run_dir(prepared)
    with lock(root), pytest.raises(ApgError, match="another writer"):
        pipeline.generate(prepared)


def test_cli_repl_parity_json_errors_and_help_are_offline(
    prepared, monkeypatch, capsys
):
    def no_network(*args, **kwargs):
        raise AssertionError("network is forbidden")

    import httpx

    monkeypatch.setattr(httpx.Client, "send", no_network)
    session = Session(json_out=True)
    assert run(session, ["data", "stats", prepared], "repl") == 0
    direct = json.loads(capsys.readouterr().out)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["data", "stats", prepared, "--json"])
    assert result.exit_code == 0 and json.loads(result.output) == direct
    result = runner.invoke(cli.app, ["data", "generate", "--help"])
    assert result.exit_code == 0
    result = runner.invoke(cli.app, ["data", "stats", "missing", "--json"])
    assert result.exit_code == 1 and "error" in json.loads(result.output)


@pytest.mark.parametrize("value", ["../escape", "C:\\escape", "a/b", "", "."])
def test_run_identifiers_cannot_escape_data_root(value):
    with pytest.raises(ApgError):
        paths.dataset_run_dir(value)


def test_empty_source_text_is_visible_but_never_support(unit_source):
    unit, standard = unit_source
    raw = candidate_for(unit, standard)
    focus = next(
        p
        for s in standard["sections"]
        for p in s["paragraphs"]
        if p["id"] == unit["focus_ids"][0]
    )
    focus["text"] = ""
    _, reasons = validation.check(raw, unit, standard)
    assert "empty_source_evidence" in reasons


def test_footnotes_never_acquire_invented_paragraph_links(unit_source):
    unit, standard = unit_source
    assert all(note["paragraph_link"] is None for note in standard["footnotes"])
    raw = candidate_for(unit, standard)
    if standard["footnotes"]:
        raw["footnote_ids"] = [standard["footnotes"][0]["id"]]
        raw["answer"] = "A fixture answer without external citations."
        record, reasons = validation.check(raw, unit, standard)
        assert not reasons
        assert record["support"][-1]["paragraph_link"] is None


def test_malformed_critic_response_cannot_accept(prepared):
    class BadCritic(provider.FixtureProvider):
        def invoke(self, stage, *args):
            response = super().invoke(stage, *args)
            if stage == "semantic":
                response["text"] = '{"checks": {}}'
            return response

    pipeline.generate(prepared)
    result = pipeline.validate(prepared, backend=BadCritic())
    assert result["accepted"] == 0
    assert result["rejection_reasons"]["malformed_critic_output"] > 0


def test_exact_duplicates_preserve_both_candidate_events(prepared):
    class Doubled(provider.FixtureProvider):
        def invoke(self, stage, *args):
            response = super().invoke(stage, *args)
            if stage == "generate":
                value = provider.decoded(response)
                value["candidates"] *= 2
                response["text"] = json.dumps(value)
            return response

    pipeline.generate(prepared, backend=Doubled())
    result = pipeline.validate(prepared)
    root = paths.dataset_run_dir(prepared)
    events = read_rows(root / "candidates.jsonl")
    assert len({event["id"] for event in events}) == len(events)
    assert result["rejection_reasons"]["exact_duplicate_question"] > 0


def test_near_duplicate_decisions_are_not_automatic_similarity_deletions(prepared):
    class Similar(provider.FixtureProvider):
        def invoke(self, stage, prompt, payload, model):
            response = super().invoke(stage, prompt, payload, model)
            if stage == "generate":
                value = provider.decoded(response)
                first = value["candidates"][0]
                second = {**first, "question": first["question"] + " Please explain."}
                value["candidates"].append(second)
                response["text"] = json.dumps(value)
            elif stage == "duplicate":
                response["text"] = json.dumps(
                    {"result": "uncertain", "reason": "Ambiguous."}
                )
            return response

    backend = Similar()
    pipeline.generate(prepared, backend=backend)
    result = pipeline.validate(prepared, backend=backend)
    assert result["rejection_reasons"]["near_duplicate_uncertain"] > 0
    assert read_rows(paths.dataset_run_dir(prepared) / "duplicates.jsonl")


def test_human_sample_balances_outcomes_and_standards():
    decisions = [
        {
            "candidate_id": f"{i:03}",
            "standard": f"AS {1000 + i % 5}",
            "status": "accepted" if i < 60 else "rejected",
            "reasons": [],
            "record": {"task_type": "definition", "complexity": {}},
        }
        for i in range(80)
    ]
    selected = reporting.sample(decisions, 40, 42)
    assert sum(d["status"] == "accepted" for d in selected) == 30
    assert len({d["standard"] for d in selected}) == 5
    assert selected != decisions[:40]


def test_request_artifact_modification_stops_resume(prepared):
    pipeline.generate(prepared)
    root = paths.dataset_run_dir(prepared)
    path = next((root / "requests").glob("*.json"))
    saved = read(path)
    saved["response"]["text"] = "tampered"
    write(path, saved)
    with pytest.raises(ApgError, match="request artifact changed"):
        pipeline.generate(prepared)


def test_unpinned_model_or_unverified_prices_are_rejected():
    with pytest.raises(ApgError, match="dated Claude"):
        Config.from_dict({"corpus_version": "2026-08", "backend": "anthropic"})
    with pytest.raises(ApgError, match="positive token prices"):
        Config.from_dict(
            {
                "corpus_version": "2026-08",
                "backend": "anthropic",
                "generator": {"model": "claude-test-20260101"},
            }
        )


def test_anthropic_adapter_with_mock_transport(monkeypatch):
    import httpx

    from apg.dataset.model import ModelConfig

    calls = []
    model = ModelConfig(model="claude-test-20260101")

    def respond(request):
        calls.append(request)
        if request.url.path.endswith("count_tokens"):
            return httpx.Response(200, json={"input_tokens": 10})
        body = json.loads(request.content)
        assert body["model"] == model.model
        assert body["max_tokens"] == 4096
        assert "tools" not in body and "thinking" not in body
        return httpx.Response(
            200,
            headers={"request-id": "test-request"},
            json={
                "model": model.model,
                "content": [{"type": "text", "text": "{}"}],
                "usage": {"input_tokens": 10, "output_tokens": 2},
                "stop_reason": "end_turn",
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key-never-sent-to-network")
    result = provider.AnthropicProvider().invoke("semantic", "prompt", {}, model)
    assert len(calls) == 2
    assert result["request_id"] == "test-request"
    assert "fixture-key" not in json.dumps(result)


def test_anthropic_count_overflow_prevents_billable_post(monkeypatch):
    import httpx

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"input_tokens": 9999999})

    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    with pytest.raises(ApgError, match="reserved input bound"):
        provider.AnthropicProvider().invoke(
            "generate", "prompt", {}, Config("2026-08").generator
        )
    assert len(calls) == 1


def test_paid_pipeline_without_approval_never_calls_provider(built_corpus, tmp_path):
    model = {
        "model": "claude-test-20260101",
        "input_usd_per_million": "1",
        "output_usd_per_million": "1",
    }
    path = tmp_path / "paid.json"
    write(
        path,
        {
            "corpus_version": "2026-08",
            "backend": "anthropic",
            "pilot_units": 1,
            "generator": model,
            "critic": model,
            "pricing_source": "test-only",
            "pricing_verified_utc": "test-only",
        },
    )
    run_id = pipeline.prepare(path)["run_id"]

    class Forbidden(provider.FixtureProvider):
        def invoke(self, *args):
            raise AssertionError("must not call provider without approval")

    with pytest.raises(ApgError, match="explicit user approval"):
        pipeline.generate(run_id, backend=Forbidden())
    assert not pipeline.requests(paths.dataset_run_dir(run_id))
    result = CliRunner().invoke(cli.app, ["data", "generate", run_id, "--json"])
    assert result.exit_code == 1
    assert "explicit approval" in json.loads(result.output)["error"]["message"]


def test_preparing_new_run_clears_previous_session_counts(
    built_corpus, tmp_path, capsys
):
    from apg.commands.data import data_prepare

    config = tmp_path / "config.json"
    write(config, {"corpus_version": "2026-08", "pilot_units": 1})
    session = Session(json_out=True, dataset_counts={"accepted": 500})
    data_prepare(session, str(config))
    assert session.dataset_counts == {"accepted": 0}
    snapshot = read(
        paths.dataset_run_dir(session.dataset_run_id) / "implementation.json"
    )
    assert snapshot["source_text"]["src/apg/dataset/pipeline.py"]
    assert snapshot["dependency_lock"]


def test_settled_invocation_releases_unused_reservation():
    budget.initialize_session("settled", "0")
    approval = budget.Approval("settled", "run-a", "generate", Decimal("2"), "one")
    budget.reserve(approval, "run-a", "generate", "a", Decimal("2"))
    budget.settle(approval, "run-a", "a", Decimal("0.1"))
    budget.reserve(approval, "run-a", "generate", "b", Decimal("1.9"))
    assert budget.remaining("settled") == Decimal("8")
    clone = budget.Approval("settled", "run-a", "generate", Decimal("2"), "one")
    with pytest.raises(ApgError, match="invocation"):
        budget.reserve(clone, "run-a", "generate", "c", Decimal("0.01"))


def test_estimate_is_offline_and_separates_bounds(built_corpus, tmp_path):
    from apg.dataset.estimation import estimate

    config = tmp_path / "estimate.json"
    write(config, {"corpus_version": "2026-08"})
    result = estimate(config)
    assert result["billable_calls"] == 0
    assert set(result["profiles"]) == {"pilot", "full"}
    for profile in result["profiles"].values():
        values = profile["forecasts"]["claude-haiku-4-5-20251001"]
        base = values[1]
        assert base["generation_usd"] == pytest.approx(
            (base["generation_input_tokens"] + base["generation_output_tokens"] * 5)
            / 1e6
        )
        assert "hard_bounds_usd" in profile
        n = profile["candidate_ceiling"]
        assert profile["duplicate_scenarios"][-1]["calls"] == n * (n - 1) // 2
    response = CliRunner().invoke(cli.app, ["--json", "data", "estimate", str(config)])
    assert response.exit_code == 0
    assert json.loads(response.stdout)["billable_calls"] == 0


def test_verify_rejects_fixture_pilot_and_corruption(prepared):
    from apg.dataset.verification import verify

    pipeline.generate(prepared)
    pipeline.validate(prepared)
    pipeline.finalize(prepared)
    result = verify(prepared)
    assert set(result["findings"]) == {"not_real_run", "not_full_profile"}
    response = CliRunner().invoke(cli.app, ["--json", "data", "verify", prepared])
    assert response.exit_code == 0
    assert not json.loads(response.stdout)["verified"]
    root = paths.dataset_run_dir(prepared)
    with (root / "accepted.jsonl").open("a") as handle:
        handle.write("{}\n")
    assert any("integrity_failure" in f for f in verify(prepared)["findings"])


def test_presubmission_and_unknown_failures_have_different_liabilities(prepared):
    from dataclasses import replace

    root, manifest, config, index, units = pipeline.load(prepared)
    config = replace(
        config,
        backend="anthropic",
        generator=replace(
            config.generator, input_usd_per_million="1", output_usd_per_million="5"
        ),
    )
    budget.initialize_session("failure", "0")
    approval = budget.Approval("failure", prepared, "generate", Decimal("10"), "one")

    class Failure:
        def __init__(self, error):
            self.error = error

        def invoke(self, *args):
            raise self.error

    for i, error in enumerate((provider.PreSubmissionError("no key"), TimeoutError())):
        with pytest.raises(type(error)):
            pipeline._request(
                root,
                manifest,
                config,
                "generate",
                str(i),
                source.context(index, units[0]),
                approval,
                Failure(error),
            )
    saved = pipeline.requests(root)
    assert {r["state"] for r in saved} == {"not_submitted", "unknown"}
    unknown = next(r for r in saved if r["state"] == "unknown")
    assert budget.remaining("failure") == Decimal("10") - Decimal(
        unknown["maximum_usd"]
    )


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("split", "split_fields_present"),
        ("duplicate", "duplicate_accepted_ids"),
        ("decision", "missing_candidate_decisions"),
        ("provenance", "group_mismatch"),
    ],
)
def test_verify_independent_checks_even_with_refreshed_hashes(
    prepared, mutation, expected
):
    from apg.dataset.storage import write_rows
    from apg.dataset.verification import verify

    pipeline.generate(prepared)
    pipeline.validate(prepared)
    pipeline.finalize(prepared)
    root = paths.dataset_run_dir(prepared)
    records = read_rows(root / "accepted.jsonl")
    if mutation == "split":
        records[0]["split"] = "train"
    elif mutation == "duplicate":
        records.append(records[0])
    elif mutation == "provenance":
        records[0]["group_key"] = "wrong"
    else:
        rows = read_rows(root / "validation.jsonl")
        write_rows(root / "validation.jsonl", rows[1:])
    write_rows(root / "accepted.jsonl", records)
    manifest = read(root / "manifest.json")
    manifest["validation_sha256"] = file_hash(root / "validation.jsonl")
    manifest["artifacts"] = {
        name: file_hash(root / name) for name in manifest["artifacts"]
    }
    write(root / "manifest.json", manifest)
    assert expected in verify(prepared)["findings"]


@pytest.mark.parametrize("command_name", ["estimate", "verify"])
def test_new_commands_share_repl_and_cli_json(command_name, monkeypatch, capsys):
    from apg.dataset import estimation, verification

    expected = {
        "run_id": "run-test",
        "verified": False,
        "findings": ["not_full_profile"],
    }
    if command_name == "estimate":
        expected = {"feasibility": "defer", "billable_calls": 0}
        monkeypatch.setattr(estimation, "estimate", lambda _: expected)
    else:
        monkeypatch.setattr(verification, "verify", lambda _: expected)
    session = Session(json_out=True)
    assert run(session, ["data", command_name, "argument"], mode="repl") == 0
    repl_result = json.loads(capsys.readouterr().out)
    result = CliRunner().invoke(cli.app, ["--json", "data", command_name, "argument"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == repl_result == expected

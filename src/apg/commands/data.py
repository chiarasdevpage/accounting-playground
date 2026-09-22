"""Dataset commands, shared by the REPL and one-shot CLI."""

from __future__ import annotations

import sys
from uuid import uuid4

from apg.console import build_table, emit
from apg.dataset import budget, pipeline
from apg.errors import ApgError
from apg.registry import Param, command
from apg.session import Session

_RUN = (Param("run_id", "prepared dataset run identifier"),)
_OPTIONAL_RUN = (Param("run_id", "dataset run identifier", required=False),)


def _selected(session: Session, run_id: str | None) -> str:
    selected = run_id or session.dataset_run_id or pipeline.latest()
    if selected is None:
        raise ApgError("no dataset selected", hint="run `data prepare <config>` first")
    return selected


def _emit(session: Session, result: dict) -> None:
    run_id = result["run_id"]
    session.dataset_run_id = run_id
    session.dataset_counts = {"accepted": result.get("accepted", 0)}
    rows = [
        [key, value]
        for key, value in result.items()
        if isinstance(value, (str, int, float, bool))
    ]
    emit(session, result, build_table("dataset", ["item", "value"], rows))


def _approval(session: Session, run_id: str, stage: str) -> budget.Approval | None:
    estimate = pipeline.estimate(run_id, stage)
    if estimate["backend"] == "fixture":
        return None
    # Config, environment variables and plan approval never authorize a charge.
    # Real execution requires a new, explicit confirmation in a human terminal.
    if session.json_out or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ApgError(
            "paid execution needs explicit approval in an interactive terminal",
            hint="inspect the prepared run and invoke this command without --json",
        )
    console = session.console
    console.print(f"Purpose: {stage} candidates for {run_id}.")
    console.print(f"Worst-case full-stage cost: ${estimate['maximum_usd']} USD.")
    console.print(
        "Actual cost depends on token usage and filtering. No retries are automatic."
    )
    console.print(
        "All project spending and unresolved commitments share a $10 session ceiling."
    )
    console.print(
        "Use the SAME session ID across runs and processes; "
        "never reset it to evade the ceiling."
    )
    if session.dataset_budget_session is None:
        session_id = input("Current spending session ID: ").strip()
        session.dataset_budget_session = session_id
    session_id = session.dataset_budget_session
    prior = input(
        "Other spending/commitments this session, excluding this ledger (USD): "
    ).strip()
    budget.initialize_session(session_id, prior)
    remaining = budget.remaining(session_id)
    console.print(f"Remaining cumulative session allowance: ${remaining} USD.")
    maximum = budget.money(
        input("Maximum USD approved for this invocation (0 to cancel): ").strip()
    )
    if maximum == 0:
        raise ApgError("paid invocation cancelled")
    if maximum > remaining:
        raise ApgError("approval would exceed the remaining session allowance")
    console.print(
        f"This invocation will stop before committing more than ${maximum} USD."
    )
    if input(
        f"Type APPROVE {stage} {run_id} to authorize this billable run: "
    ).strip() != (f"APPROVE {stage} {run_id}"):
        raise ApgError("paid invocation was not approved")
    return budget.Approval(session_id, run_id, stage, maximum, uuid4().hex)


@command(
    "data prepare",
    "Prepare and verify an offline dataset run.",
    params=(Param("config", "path to a JSON generation configuration"),),
)
def data_prepare(session: Session, config: str) -> None:
    _emit(session, pipeline.prepare(config))


@command(
    "data generate",
    "Generate raw candidates; paid backends require approval.",
    params=_RUN,
)
def data_generate(session: Session, run_id: str) -> None:
    _emit(session, pipeline.generate(run_id, _approval(session, run_id, "generate")))


@command(
    "data validate", "Validate candidates and resolve probable duplicates.", params=_RUN
)
def data_validate(session: Session, run_id: str) -> None:
    _emit(session, pipeline.validate(run_id, _approval(session, run_id, "validate")))


@command(
    "data finalize", "Finalize an immutable, unsplit accepted dataset.", params=_RUN
)
def data_finalize(session: Session, run_id: str) -> None:
    _emit(session, pipeline.finalize(run_id))


@command(
    "data stats",
    "Show dataset acceptance, coverage and rejection counts.",
    params=_OPTIONAL_RUN,
)
def data_stats(session: Session, run_id: str | None = None) -> None:
    _emit(session, pipeline.stats(_selected(session, run_id)))


@command(
    "data sample",
    "Create a seeded review sample with full evidence.",
    params=_OPTIONAL_RUN,
)
def data_sample(session: Session, run_id: str | None = None) -> None:
    selected = _selected(session, run_id)
    result = pipeline.review(selected)
    # A review sample's accepted count is not the dataset's accepted count.
    session.dataset_counts = {"accepted": pipeline.stats(selected)["accepted"]}
    emit(
        session,
        result,
        build_table(
            "dataset review",
            ["item", "value"],
            [
                ["run", selected],
                ["HTML", result["review_html"]],
                ["sample size", result["actual"]],
            ],
        ),
    )
    session.dataset_run_id = selected


@command(
    "data estimate",
    "Estimate pilot and production costs without generation.",
    params=(Param("config", "path to JSON configuration"),),
)
def data_estimate(session: Session, config: str) -> None:
    from apg.dataset.estimation import estimate

    result = estimate(config)
    emit(session, result, result["feasibility"])


@command(
    "data verify", "Independently verify a finalized production dataset.", params=_RUN
)
def data_verify(session: Session, run_id: str) -> None:
    from apg.dataset.verification import verify

    _emit(session, verify(run_id))

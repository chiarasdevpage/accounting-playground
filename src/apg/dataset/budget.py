"""Explicit per-invocation approval and durable cumulative session commitments.

An Approval is issued by the interactive confirmation surface, never read from
generation configuration. All paid requests share the session ledger lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apg import paths
from apg.dataset.storage import lock, read, safe_id, write
from apg.errors import ApgError

CEILING = Decimal("10")


def money(value: str) -> Decimal:
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except (ValueError, ArithmeticError) as exc:
        raise ApgError("cost must be a finite nonnegative USD amount") from exc


@dataclass
class Approval:
    session_id: str
    run_id: str
    stage: str
    approved_usd: Decimal
    invocation_id: str
    committed_usd: Decimal = Decimal("0")


def initialize_session(session_id: str, prior_usd: str) -> None:
    root = paths.budget_dir() / safe_id(session_id)
    prior = money(prior_usd)
    if prior > CEILING:
        raise ApgError("session spending already exceeds the project ceiling")
    with lock(root):
        path = root / "ledger.json"
        if path.exists():
            ledger = read(path)
            # Never lower previously reported outside spending.
            ledger["prior_usd"] = str(max(prior, money(ledger["prior_usd"])))
        else:
            ledger = {"prior_usd": str(prior), "requests": {}}
        write(path, ledger)


def total(ledger: dict) -> Decimal:
    return money(ledger["prior_usd"]) + sum(
        (
            money(item.get("actual_usd", item["reserved_usd"]))
            for item in ledger["requests"].values()
        ),
        Decimal("0"),
    )


def remaining(session_id: str) -> Decimal:
    path = paths.budget_dir() / safe_id(session_id) / "ledger.json"
    return CEILING - total(read(path))


def reserve(
    approval: Approval | None,
    run_id: str,
    stage: str,
    request_id: str,
    maximum: Decimal,
) -> None:
    if approval is None or approval.run_id != run_id or approval.stage != stage:
        raise ApgError("this billable invocation requires explicit user approval")
    root = paths.budget_dir() / safe_id(approval.session_id)
    with lock(root):
        path = root / "ledger.json"
        ledger = read(path)
        if any(
            item["state"] == "pricing_discrepancy"
            for item in ledger["requests"].values()
        ):
            raise ApgError("unresolved pricing discrepancy blocks further paid work")
        invocation = [
            item
            for item in ledger["requests"].values()
            if item["invocation_id"] == approval.invocation_id
        ]
        if any(
            money(item["approved_usd"]) != approval.approved_usd for item in invocation
        ):
            raise ApgError("invocation approval amount changed")
        committed = sum(
            (
                money(item.get("actual_usd", item["reserved_usd"]))
                for item in invocation
            ),
            Decimal("0"),
        )
        if committed + maximum > approval.approved_usd:
            raise ApgError("request would exceed this invocation's approved maximum")
        key = f"{run_id}:{request_id}"
        if key in ledger["requests"]:
            raise ApgError("request already committed; do not automatically resend")
        if total(ledger) + maximum > CEILING:
            raise ApgError("request would exceed the $10 cumulative session ceiling")
        ledger["requests"][key] = {
            "reserved_usd": str(maximum),
            "state": "reserved",
            "invocation_id": approval.invocation_id,
            "approved_usd": str(approval.approved_usd),
            "stage": stage,
        }
        write(path, ledger)
        approval.committed_usd = committed + maximum


def settle(approval: Approval, run_id: str, request_id: str, actual: Decimal) -> None:
    root = paths.budget_dir() / safe_id(approval.session_id)
    with lock(root):
        path = root / "ledger.json"
        ledger = read(path)
        item = ledger["requests"][f"{run_id}:{request_id}"]
        if actual > money(item["reserved_usd"]):
            # Record the provider discrepancy; never hide it or continue spending.
            item["actual_usd"] = str(actual)
            item["state"] = "pricing_discrepancy"
            write(path, ledger)
            raise ApgError("provider usage exceeded the reserved bound; stop paid work")
        item["actual_usd"] = str(actual)
        item["state"] = "settled"
        write(path, ledger)

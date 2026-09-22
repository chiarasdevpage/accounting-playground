"""Replaceable provider boundary and an explicitly labelled offline fixture.

No automatic retries, tools, caching, thinking, or asynchronous billable jobs.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Protocol

from apg.dataset.model import CRITERIA, ModelConfig
from apg.dataset.storage import canonical
from apg.errors import ApgError


def input_bound(prompt: str, payload: dict) -> int:
    # Conservative preview; verified against the provider's free token-count
    # endpoint before sending a billable request. Never assume words == tokens.
    return len((prompt + canonical(payload)).encode("utf-8")) + 1024


def maximum_cost(model: ModelConfig, input_tokens: int) -> Decimal:
    return (
        Decimal(model.input_usd_per_million) * input_tokens
        + Decimal(model.output_usd_per_million) * model.max_output_tokens
    ) / Decimal(1000000)


class Provider(Protocol):
    def invoke(
        self, stage: str, prompt: str, payload: dict, model: ModelConfig
    ) -> dict: ...


class FixtureProvider:
    """Exercises artifact plumbing. Its decisions are NOT scientific validation."""

    def invoke(
        self, stage: str, prompt: str, payload: dict, model: ModelConfig
    ) -> dict:
        if stage == "generate":
            unit = payload["unit"]
            paragraphs = [
                p for s in payload["source"]["sections"] for p in s["paragraphs"]
            ]
            focus = next(p for p in paragraphs if p["id"] == unit["focus_ids"][0])
            output = {
                "candidates": [
                    {
                        "question": f"What does {focus['citation']} state?",
                        "answer": focus["text"],
                        "task_type": "direct_requirement",
                        "paragraph_ids": [focus["id"]],
                        "footnote_ids": [],
                        "reasoning_tags": [],
                    }
                ],
                "abstention_reason": None,
            }
        elif stage == "semantic":
            output = {
                "checks": {
                    key: {
                        "result": "pass",
                        "reason": "Fixture decision, not a real critic.",
                        "evidence_ids": payload["candidate"]["paragraph_ids"],
                    }
                    for key in CRITERIA
                }
            }
        else:
            output = {"result": "distinct", "reason": "Fixture-only decision."}
        return {
            "text": canonical(output),
            "raw": output,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "model": model.model,
            "request_id": "fixture",
            "stop_reason": "end_turn",
        }


class PreSubmissionError(ApgError):
    """Proven failure before the billable messages endpoint was called."""


class AnthropicProvider:
    def invoke(
        self, stage: str, prompt: str, payload: dict, model: ModelConfig
    ) -> dict:
        import httpx

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise PreSubmissionError("ANTHROPIC_API_KEY is not set")
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        messages = [{"role": "user", "content": canonical(payload)}]
        base = {"model": model.model, "system": prompt, "messages": messages}
        with httpx.Client(timeout=120, follow_redirects=False) as client:
            try:
                # This endpoint counts tokens, does not generate text, and is free.
                count = client.post(
                    "https://api.anthropic.com/v1/messages/count_tokens",
                    headers=headers,
                    json=base,
                )
                count.raise_for_status()
                tokens = count.json()["input_tokens"]
                if (
                    type(tokens) is not int
                    or tokens < 0
                    or tokens > input_bound(prompt, payload)
                ):
                    raise ApgError(
                        "provider token count exceeds the reserved input bound"
                    )
                if tokens + model.max_output_tokens > model.context_tokens:
                    raise ApgError("request does not fit configured model context")
            except ApgError as exc:
                raise PreSubmissionError(str(exc)) from exc
            except Exception as exc:
                raise PreSubmissionError(
                    "free token preflight failed before submission"
                ) from exc
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    **base,
                    "max_tokens": model.max_output_tokens,
                    "temperature": model.temperature,
                },
            )
            response.raise_for_status()
            raw = response.json()
            text = "".join(
                block.get("text", "")
                for block in raw.get("content", [])
                if block.get("type") == "text"
            )
            return {
                "text": text,
                "raw": raw,
                "usage": raw["usage"],
                "model": raw["model"],
                "request_id": response.headers.get("request-id"),
                "stop_reason": raw.get("stop_reason"),
            }


def decoded(response: dict) -> object:
    if response.get("stop_reason") != "end_turn":
        raise ValueError("incomplete_model_response")
    return json.loads(response["text"])

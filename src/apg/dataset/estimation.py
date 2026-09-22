"""Nonbillable, reproducible forecasts; assumptions are never spending approval."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from apg.dataset import prompts, provider, source
from apg.dataset.model import Config
from apg.dataset.storage import canonical, digest, read


def estimate(config_path: str | Path) -> dict:
    config = Config.from_dict(read(Path(config_path)))
    index = source.inspect(config.corpus_version)
    snapshot = prompts.snapshot()
    profiles = {}
    for profile in ("pilot", "full"):
        units = source.units(index, replace(config, profile=profile))
        measurements = []
        for unit in units:
            payload = source.context(index, unit)
            measurements.append(
                {
                    "unit_id": unit["id"],
                    "standard": unit["standard"],
                    "candidate_limit": unit["candidate_limit"],
                    "request_sha256": digest([snapshot["generator"], payload]),
                    "generator_input_bytes": len(
                        (snapshot["generator"] + canonical(payload)).encode()
                    ),
                    "critic_base_input_bytes": len(
                        (snapshot["critic"] + canonical(payload)).encode()
                    ),
                    "generator_input_bound": provider.input_bound(
                        snapshot["generator"], payload
                    ),
                }
            )
        n = sum(u["candidate_limit"] for u in units)
        pairs = n * (n - 1) // 2
        comparisons = {}
        for name, inp, out in (
            ("claude-haiku-4-5-20251001", 1, 5),
            ("claude-sonnet-5", 2, 10),
        ):
            scenarios = []
            for yield_fraction in (0.5, 1.0):
                for output_length in (350, 700):
                    generation_input = sum(
                        m["generator_input_bytes"] / 4 for m in measurements
                    )
                    semantic_input = sum(
                        m["candidate_limit"]
                        * yield_fraction
                        * (m["critic_base_input_bytes"] / 4 + output_length)
                        for m in measurements
                    )
                    generation_output = n * yield_fraction * output_length
                    semantic_output = n * yield_fraction * 500
                    generation = (
                        generation_input * inp + generation_output * out
                    ) / 1e6
                    semantic = (semantic_input * inp + semantic_output * out) / 1e6
                    scenarios.append(
                        {
                            "candidate_yield": yield_fraction,
                            "candidate_tokens": output_length,
                            "generation_input_tokens": generation_input,
                            "generation_output_tokens": generation_output,
                            "semantic_input_tokens": semantic_input,
                            "semantic_output_tokens": semantic_output,
                            "generation_usd": generation,
                            "semantic_usd": semantic,
                            "total_before_duplicates_usd": generation + semantic,
                        }
                    )
            comparisons[name] = scenarios
        critic_max = provider.maximum_cost(
            config.critic,
            config.critic.context_tokens - config.critic.max_output_tokens,
        )
        profiles[profile] = {
            "units": len(units),
            "standards": len({u["standard"] for u in units}),
            "candidate_ceiling": n,
            "measurements": measurements,
            "forecasts": comparisons,
            "hard_bounds_usd": {
                "generation": str(
                    sum(
                        (
                            provider.maximum_cost(
                                config.generator, m["generator_input_bound"]
                            )
                            for m in measurements
                        ),
                        Decimal(0),
                    )
                ),
                "semantic": str(critic_max * n),
                "duplicate": str(critic_max * pairs),
            },
            "output_allowances": {
                "generation_per_request": config.generator.max_output_tokens,
                "critic_per_request": config.critic.max_output_tokens,
            },
            "duplicate_scenarios": [
                {"calls": calls, "maximum_usd": str(critic_max * calls)}
                for calls in (0, n, pairs)
            ],
        }
    totals = {
        name: [
            sum(
                profiles[p]["forecasts"][name][i]["total_before_duplicates_usd"]
                for p in profiles
            )
            for i in range(4)
        ]
        for name in profiles["pilot"]["forecasts"]
    }
    return {
        "schema_version": 1,
        "config": config.to_dict(),
        "prompt_sha256": digest(snapshot),
        "corpus_fingerprint": index["fingerprint"],
        "parsed_fingerprint": index["parsed_fingerprint"],
        "measurement_method": (
            "UTF-8 bytes / 4 heuristic; NOT provider token counts or a quote"
        ),
        "pricing_status": "user-supplied planning rates; reverify before approval",
        "assumptions": {
            "bytes_per_token": 4,
            "critic_output_tokens": 500,
            "retries": 0,
            "cache": "disabled; reservations assume misses",
        },
        "profiles": profiles,
        "pilot_plus_production_before_duplicates_usd": totals,
        "feasibility": (
            "not established; defer paid work pending exact token counts "
            "and complete-workflow bound"
        ),
        "pilot_plus_production_hard_bounds_usd": {
            stage: str(
                sum(
                    (Decimal(profiles[p]["hard_bounds_usd"][stage]) for p in profiles),
                    Decimal(0),
                )
            )
            for stage in ("generation", "semantic", "duplicate")
        },
        "billable_calls": 0,
    }

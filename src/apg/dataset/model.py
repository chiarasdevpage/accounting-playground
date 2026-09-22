"""Versioned configuration and record contracts, independent of terminal UI."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from apg.errors import ApgError

SCHEMA_VERSION = 1
TASK_TYPES = (
    "direct_requirement",
    "definition",
    "condition",
    "exception",
    "relationship",
    "distinction",
    "multi_paragraph_synthesis",
    "application",
    "scenario",
    "citation_lookup",
)
CRITERIA = (
    "answerable",
    "supported",
    "unambiguous",
    "complete",
    "source_only",
    "citations_correct",
    "qa_agreement",
    "scenario_explicit",
    "single_part",
)


@dataclass(frozen=True)
class ModelConfig:
    model: str = "fixture-v1"
    max_output_tokens: int = 4096
    context_tokens: int = 200000
    temperature: float = 0.0
    input_usd_per_million: str = "0"
    output_usd_per_million: str = "0"

    def validate(self, backend: str) -> None:
        from decimal import Decimal, InvalidOperation

        if (
            type(self.max_output_tokens) is not int
            or type(self.context_tokens) is not int
            or self.max_output_tokens < 1
            or self.context_tokens <= self.max_output_tokens
            or not isinstance(self.temperature, (int, float))
            or not 0 <= self.temperature <= 1
        ):
            raise ApgError("invalid model token limits or temperature")
        try:
            rates = [
                Decimal(self.input_usd_per_million),
                Decimal(self.output_usd_per_million),
            ]
            if any(not rate.is_finite() or rate < 0 for rate in rates):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ApgError("model prices must be nonnegative decimal strings") from exc
        if backend == "anthropic":
            if not isinstance(self.model, str) or not re.fullmatch(
                r"claude-[a-z0-9-]+-\d{8}", self.model
            ):
                raise ApgError("real runs require a dated Claude model identifier")
            if any(rate == 0 for rate in rates):
                raise ApgError("real runs require verified, positive token prices")


@dataclass(frozen=True)
class Config:
    corpus_version: str
    backend: str = "fixture"
    profile: str = "pilot"
    seed: int = 42
    words_per_candidate: int = 150
    max_candidates: int = 8
    pilot_units: int = 24
    review_size: int = 40
    generator: ModelConfig = field(default_factory=ModelConfig)
    critic: ModelConfig = field(default_factory=ModelConfig)
    unigram_threshold: float = 0.70
    bigram_threshold: float = 0.50
    pricing_source: str = ""
    pricing_verified_utc: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> Config:
        try:
            data = dict(raw)
            for key in ("generator", "critic"):
                if key in data:
                    data[key] = ModelConfig(**data[key])
            config = cls(**data)
        except (TypeError, ValueError) as exc:
            raise ApgError(f"invalid generation configuration: {exc}") from exc
        from apg.dataset.storage import safe_id

        safe_id(config.corpus_version)
        if config.backend not in {"fixture", "anthropic"}:
            raise ApgError("backend must be fixture or anthropic")
        if config.profile not in {"pilot", "full"}:
            raise ApgError("profile must be pilot or full")
        for key in ("words_per_candidate", "pilot_units", "review_size"):
            if type(getattr(config, key)) is not int or getattr(config, key) < 1:
                raise ApgError(f"{key} must be a positive integer")
        if type(config.seed) is not int:
            raise ApgError("seed must be an integer")
        if (
            type(config.max_candidates) is not int
            or not 2 <= config.max_candidates <= 8
        ):
            raise ApgError("max_candidates must be between 2 and 8")
        if any(
            not isinstance(v, (float, int)) or not 0 < v <= 1
            for v in (config.unigram_threshold, config.bigram_threshold)
        ):
            raise ApgError("duplicate thresholds must be in (0, 1]")
        config.generator.validate(config.backend)
        config.critic.validate(config.backend)
        if config.backend == "anthropic" and not (
            config.pricing_source and config.pricing_verified_utc
        ):
            raise ApgError("real configurations must record pricing evidence and date")
        return config

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Candidate:
    question: str
    answer: str
    task_type: str
    paragraph_ids: list[str]
    footnote_ids: list[str] = field(default_factory=list)
    reasoning_tags: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: object) -> Candidate:
        if not isinstance(raw, dict):
            raise ValueError("candidate_not_object")
        if set(raw) - set(cls.__dataclass_fields__):
            raise ValueError("unexpected_fields")
        try:
            candidate = cls(**raw)
        except TypeError as exc:
            raise ValueError("missing_fields") from exc
        for name in ("question", "answer", "task_type"):
            value = getattr(candidate, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"empty_or_invalid_{name}")
            if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
                raise ValueError("control_characters")
        if candidate.task_type not in TASK_TYPES:
            raise ValueError("unknown_task_type")
        for name in ("paragraph_ids", "footnote_ids", "reasoning_tags"):
            values = getattr(candidate, name)
            if (
                not isinstance(values, list)
                or any(not isinstance(value, str) or not value for value in values)
                or len(values) != len(set(values))
            ):
                raise ValueError(f"invalid_{name}")
        if not candidate.paragraph_ids:
            raise ValueError("missing_paragraph_evidence")
        if set(candidate.reasoning_tags) - set(TASK_TYPES):
            raise ValueError("unknown_reasoning_tag")
        return candidate

    def to_dict(self) -> dict:
        return asdict(self)

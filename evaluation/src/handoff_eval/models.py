from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONDITIONS = frozenset({"c0", "c1", "c2"})


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    extra = set(value) - expected
    missing = expected - set(value)
    if extra or missing:
        raise ValueError(
            f"{context} schema mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


@dataclass(frozen=True)
class AgentResult:
    schema_version: int
    scenario_id: str
    condition: str
    claims: tuple[dict[str, Any], ...]
    next_actions: tuple[str, ...]
    unknowns: tuple[str, ...]
    metrics: dict[str, int | None]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentResult:
        _exact_keys(
            value,
            {"schema_version", "scenario_id", "condition", "answer", "metrics"},
            "result",
        )
        if value["schema_version"] != 1:
            raise ValueError("unsupported result schema_version")
        if value["condition"] not in CONDITIONS:
            raise ValueError("condition must be c0, c1, or c2")
        answer = value["answer"]
        if not isinstance(answer, dict):
            raise ValueError("answer must be an object")
        _exact_keys(answer, {"claims", "next_actions", "unknowns"}, "answer")
        claims: list[dict[str, Any]] = []
        for claim in answer["claims"]:
            if not isinstance(claim, dict):
                raise ValueError("claim must be an object")
            _exact_keys(claim, {"key", "value", "citations"}, "claim")
            if not isinstance(claim["citations"], list):
                raise ValueError("claim citations must be a list")
            claims.append(claim)
        metrics = value["metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be an object")
        _exact_keys(metrics, {"tokens", "steps", "duration_ms"}, "metrics")
        for name, metric in metrics.items():
            if metric is not None and (not isinstance(metric, int) or metric < 0):
                raise ValueError(f"metric {name} must be a non-negative integer or null")
        return cls(
            schema_version=1,
            scenario_id=str(value["scenario_id"]),
            condition=str(value["condition"]),
            claims=tuple(claims),
            next_actions=tuple(str(item) for item in answer["next_actions"]),
            unknowns=tuple(str(item) for item in answer["unknowns"]),
            metrics=metrics,
        )

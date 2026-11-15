from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .models import AgentResult


def normalize(value: Any) -> str:
    return " ".join(str(value).strip().casefold().split())


def grade_result(scenario_root: Path, bundle: Path, result_path: Path) -> dict[str, Any]:
    rubric = read_json(scenario_root / "hidden" / "rubric.json")
    result = AgentResult.from_dict(read_json(result_path))
    condition = read_json(bundle / "condition.json")
    if result.scenario_id != condition["scenario_id"] or result.condition != condition["condition"]:
        raise ValueError("result scenario or condition does not match bundle")

    claims = {normalize(item["key"]): item for item in result.claims}
    required = rubric["required_claims"]
    required_hits: list[str] = []
    omissions: list[str] = []
    for key, allowed in required.items():
        claim = claims.get(normalize(key))
        if claim and normalize(claim["value"]) in {normalize(value) for value in allowed}:
            required_hits.append(key)
        else:
            omissions.append(key)

    forbidden_hits = []
    for item in rubric["forbidden_claims"]:
        claim = claims.get(normalize(item["key"]))
        if claim and normalize(claim["value"]) in {normalize(value) for value in item["values"]}:
            forbidden_hits.append(item["key"])

    supported = {normalize(key) for key in rubric.get("supported_claims", required)}
    unsupported = [item["key"] for item in result.claims if normalize(item["key"]) not in supported]
    normalized_actions = {normalize(item) for item in result.next_actions}
    action_hits = [
        action for action in rubric["required_actions"] if normalize(action) in normalized_actions
    ]
    unknown_values = {normalize(item) for item in result.unknowns}
    unknown_hits = [
        item for item in rubric["expected_unknowns"] if normalize(item) in unknown_values
    ]
    valid_refs = set(rubric["valid_citations"])
    used_refs = [ref for claim in result.claims for ref in claim["citations"]]
    valid_citations = [ref for ref in used_refs if ref in valid_refs]
    invalid_citations = [ref for ref in used_refs if ref not in valid_refs]

    score = (
        len(required_hits) * 3
        + len(action_hits) * 2
        + len(unknown_hits)
        + len(set(valid_citations))
        - len(forbidden_hits) * 3
        - len(unsupported) * 2
        - len(invalid_citations)
    )
    grade = {
        "schema_version": 1,
        "scenario_id": result.scenario_id,
        "condition": result.condition,
        "required_hits": required_hits,
        "omissions": omissions,
        "forbidden_hits": forbidden_hits,
        "required_action_hits": action_hits,
        "unsupported_claims": unsupported,
        "unknown_hits": unknown_hits,
        "valid_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "score": score,
        "pass": score >= int(rubric["pass_score"]) and not forbidden_hits,
        "metrics": result.metrics,
    }
    return grade


def grade_to_file(
    scenario_root: Path, bundle: Path, result_path: Path, output_path: Path
) -> dict[str, Any]:
    grade = grade_result(scenario_root, bundle, result_path)
    write_json(output_path, grade)
    return grade

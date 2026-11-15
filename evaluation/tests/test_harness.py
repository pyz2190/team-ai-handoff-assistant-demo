from __future__ import annotations

import json
from pathlib import Path

import pytest

from handoff_eval.grade import grade_result
from handoff_eval.io import ensure_safe_tree, file_hash, read_json
from handoff_eval.models import AgentResult
from handoff_eval.prepare import prepare_scenario
from handoff_eval.summarize import summarize

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def test_prepare_isolates_conditions_and_hidden_rubric(tmp_path):
    root = SCENARIOS / "policy-context"
    bundles = prepare_scenario(root, tmp_path)
    assert not (bundles["c0"] / "raw_events.jsonl").exists()
    assert not (bundles["c0"] / "handoff.json").exists()
    assert (bundles["c1"] / "raw_events.jsonl").exists()
    assert not (bundles["c1"] / "handoff.json").exists()
    assert (bundles["c2"] / "handoff.json").exists()
    assert (bundles["c2"] / "citations.json").exists()
    assert all(not list(bundle.rglob("rubric.json")) for bundle in bundles.values())
    (bundles["c0"] / "raw_events.jsonl").write_text("leak", encoding="utf-8")
    refreshed = prepare_scenario(root, tmp_path)
    assert not (refreshed["c0"] / "raw_events.jsonl").exists()


def test_result_schema_rejects_extra_fields():
    value = read_json(SCENARIOS / "easy-inferable" / "fixtures" / "c0.json")
    value["unexpected"] = True
    with pytest.raises(ValueError, match="schema mismatch"):
        AgentResult.from_dict(value)


def test_bundle_scanner_rejects_hidden_rubric(tmp_path):
    leaked = tmp_path / "bundle" / "hidden" / "rubric.json"
    leaked.parent.mkdir(parents=True)
    leaked.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden file"):
        ensure_safe_tree(tmp_path / "bundle", {"rubric.json", "hidden"})


def test_synthetic_benchmarks_expose_when_handoff_helps(tmp_path):
    easy = SCENARIOS / "easy-inferable"
    easy_bundles = prepare_scenario(easy, tmp_path)
    easy_c0 = grade_result(easy, easy_bundles["c0"], easy / "fixtures" / "c0.json")
    easy_c2 = grade_result(easy, easy_bundles["c2"], easy / "fixtures" / "c2.json")
    assert easy_c0["pass"] and easy_c2["pass"]
    assert easy_c0["score"] == easy_c2["score"]

    policy = SCENARIOS / "policy-context"
    policy_bundles = prepare_scenario(policy, tmp_path)
    c0 = grade_result(policy, policy_bundles["c0"], policy / "fixtures" / "c0.json")
    c1 = grade_result(policy, policy_bundles["c1"], policy / "fixtures" / "c1.json")
    c2 = grade_result(policy, policy_bundles["c2"], policy / "fixtures" / "c2.json")
    assert not c0["pass"]
    assert c1["pass"] and c2["pass"]
    assert c0["forbidden_hits"] == ["notification_policy"]


def test_grading_and_summary_are_deterministic_and_preserve_unknown_metrics(tmp_path):
    root = SCENARIOS / "easy-inferable"
    bundle = prepare_scenario(root, tmp_path)["c0"]
    result_path = root / "fixtures" / "c0.json"
    first = grade_result(root, bundle, result_path)
    second = grade_result(root, bundle, result_path)
    assert first == second
    first["metrics"]["tokens"] = None
    grade_path = tmp_path / "grades" / "easy" / "c0" / "grade.json"
    grade_path.parent.mkdir(parents=True)
    grade_path.write_text(json.dumps(first), encoding="utf-8")
    summary = summarize(tmp_path / "grades", tmp_path / "report")
    assert summary["runs"][0]["tokens"] is None
    assert "unknown" in (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    before = file_hash(tmp_path / "report" / "summary.json")
    summarize(tmp_path / "grades", tmp_path / "report")
    assert before == file_hash(tmp_path / "report" / "summary.json")

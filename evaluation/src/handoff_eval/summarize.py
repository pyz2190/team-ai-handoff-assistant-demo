from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json, write_json


def show_metric(value: object) -> str:
    return "unknown" if value is None else str(value)


def summarize(grades_root: Path, output_root: Path) -> dict[str, Any]:
    grades = [read_json(path) for path in sorted(grades_root.rglob("grade.json"))]
    rows = []
    for grade in grades:
        metrics = grade["metrics"]
        rows.append(
            {
                "scenario_id": grade["scenario_id"],
                "condition": grade["condition"],
                "pass": grade["pass"],
                "score": grade["score"],
                "omissions": len(grade["omissions"]),
                "unsupported_claims": len(grade["unsupported_claims"]),
                "valid_citations": len(grade["valid_citations"]),
                "invalid_citations": len(grade["invalid_citations"]),
                "tokens": metrics.get("tokens"),
                "steps": metrics.get("steps"),
                "duration_ms": metrics.get("duration_ms"),
            }
        )
    summary = {"schema_version": 1, "runs": rows}
    write_json(output_root / "summary.json", summary)
    lines = [
        "# C0/C1/C2 Evaluation Report",
        "",
        "| Scenario | Condition | Pass | Score | Omissions | Unsupported | "
        "Citations | Tokens | Steps | Duration ms |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scenario_id']} | {row['condition'].upper()} | "
            f"{'yes' if row['pass'] else 'no'} | {row['score']} | {row['omissions']} | "
            f"{row['unsupported_claims']} | {row['valid_citations']}/{row['invalid_citations']} | "
            f"{show_metric(row['tokens'])} | {show_metric(row['steps'])} | "
            f"{show_metric(row['duration_ms'])} |"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return summary

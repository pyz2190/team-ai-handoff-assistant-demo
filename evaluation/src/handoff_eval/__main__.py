from __future__ import annotations

import argparse
from pathlib import Path

from .grade import grade_to_file
from .io import read_json
from .prepare import prepare_scenario
from .summarize import summarize


def scenario_roots(base: Path, selected: str) -> list[Path]:
    if selected == "all":
        return sorted(path for path in base.iterdir() if (path / "scenario.json").exists())
    root = base / selected
    if not (root / "scenario.json").exists():
        raise ValueError(f"unknown scenario: {selected}")
    return [root]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="handoff_eval")
    result.add_argument(
        "--scenarios-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "scenarios",
    )
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("prepare", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--scenario", default="all")
        command.add_argument("--out", type=Path, required=True)
    grade = commands.add_parser("grade")
    grade.add_argument("--scenario", required=True)
    grade.add_argument("--condition", choices=("c0", "c1", "c2"), required=True)
    grade.add_argument("--bundle", type=Path, required=True)
    grade.add_argument("--result", type=Path, required=True)
    grade.add_argument("--out", type=Path, required=True)
    report = commands.add_parser("summarize")
    report.add_argument("--runs", type=Path, required=True)
    report.add_argument("--out", type=Path, required=True)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "prepare":
        for root in scenario_roots(args.scenarios_dir, args.scenario):
            prepare_scenario(root, args.out)
        return
    if args.command == "smoke":
        for root in scenario_roots(args.scenarios_dir, args.scenario):
            scenario_id = str(read_json(root / "scenario.json")["id"])
            bundles = prepare_scenario(root, args.out)
            for condition, bundle in bundles.items():
                grade_to_file(
                    root,
                    bundle,
                    root / "fixtures" / f"{condition}.json",
                    args.out / scenario_id / "grades" / condition / "grade.json",
                )
        return
    if args.command == "grade":
        root = scenario_roots(args.scenarios_dir, args.scenario)[0]
        grade_to_file(root, args.bundle, args.result, args.out)
        return
    summarize(args.runs, args.out)


if __name__ == "__main__":
    main()

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .io import ensure_safe_tree, file_hash, read_json, write_json
from .models import CONDITIONS

CONDITION_FILES = {
    "c0": (),
    "c1": ("raw_events.jsonl",),
    "c2": ("handoff.json", "citations.json"),
}


def _copy_checked(source: Path, destination: Path, scenario_root: Path) -> None:
    source_resolved = source.resolve()
    root_resolved = scenario_root.resolve()
    if source.is_symlink() or root_resolved not in source_resolved.parents:
        raise ValueError(f"unsafe scenario source: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def prepare_scenario(scenario_root: Path, output_root: Path) -> dict[str, Path]:
    metadata = read_json(scenario_root / "scenario.json")
    scenario_id = str(metadata["id"])
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", scenario_id) is None:
        raise ValueError("scenario id must be a safe lowercase slug")
    destinations: dict[str, Path] = {}
    for condition in sorted(CONDITIONS):
        destination = output_root / scenario_id / condition
        resolved_output = output_root.resolve()
        if resolved_output not in destination.resolve().parents:
            raise ValueError("condition output escapes requested root")
        if destination.is_symlink():
            raise ValueError("condition output cannot be a symbolic link")
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        _copy_checked(scenario_root / "task.md", destination / "task.md", scenario_root)
        public = scenario_root / "public"
        for source in sorted(public.rglob("*")):
            if source.is_file():
                _copy_checked(
                    source, destination / "public" / source.relative_to(public), scenario_root
                )
        for filename in CONDITION_FILES[condition]:
            _copy_checked(scenario_root / filename, destination / filename, scenario_root)
        write_json(
            destination / "condition.json",
            {"schema_version": 1, "scenario_id": scenario_id, "condition": condition},
        )
        ensure_safe_tree(destination, {"rubric.json", "hidden"})
        files = {
            path.relative_to(destination).as_posix(): file_hash(path)
            for path in sorted(destination.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }
        write_json(
            destination / "manifest.json",
            {
                "schema_version": 1,
                "scenario_id": scenario_id,
                "condition": condition,
                "files": files,
            },
        )
        destinations[condition] = destination
    return destinations

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_safe_tree(root: Path, forbidden_names: set[str] | None = None) -> None:
    resolved_root = root.resolve()
    forbidden = forbidden_names or set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic link is not allowed: {path}")
        resolved = path.resolve()
        if resolved_root not in resolved.parents and resolved != resolved_root:
            raise ValueError(f"path escapes bundle: {path}")
        if path.name in forbidden:
            raise ValueError(f"forbidden file leaked into bundle: {path.name}")

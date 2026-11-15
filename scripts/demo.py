"""Build and run the single-port local demo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    python = sys.executable
    run(["npm.cmd", "run", "build"], FRONTEND)
    run([python, "-m", "alembic", "upgrade", "head"], BACKEND)
    print("Demo: http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    try:
        return subprocess.call(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=BACKEND,
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

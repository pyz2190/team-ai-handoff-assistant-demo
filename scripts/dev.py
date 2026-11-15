"""Start the FastAPI API and Vite frontend for local development."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def main() -> int:
    python = sys.executable
    processes = [
        subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
            cwd=BACKEND,
        ),
        subprocess.Popen(["npm.cmd", "run", "dev"], cwd=FRONTEND),
    ]
    print("API: http://127.0.0.1:8000/docs")
    print("Web: http://127.0.0.1:5173")
    try:
        return max(process.wait() for process in processes)
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

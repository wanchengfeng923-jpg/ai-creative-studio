"""发布前本地验证门禁。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_gate() -> list[tuple[str, int]]:
    commands = [
        ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], "unittest"),
        (["node", "--check", "static/app.js"], "node"),
        ([sys.executable, "-m", "compileall", "-q", "src", "chat2api"], "compileall"),
        ([sys.executable, "-m", "creative_studio.phase5_governance"], "governance"),
        ([sys.executable, "-m", "creative_studio.evaluation_harness", "--validate-only"], "evaluation"),
        ([sys.executable, "-m", "creative_studio.backup", "--dry-run", "--output", ".scratch/backup-smoke"], "backup-dry-run"),
        (["git", "diff", "--check"], "diff-check"),
    ]
    results: list[tuple[str, int]] = []
    environment = dict(__import__("os").environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    for command, name in commands:
        completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        results.append((name, int(completed.returncode)))
        if completed.returncode:
            break
    return results


def main() -> int:
    results = run_gate()
    for name, code in results:
        print(f"{name}: {'ok' if code == 0 else 'failed'}")
    return 0 if results and all(code == 0 for _, code in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

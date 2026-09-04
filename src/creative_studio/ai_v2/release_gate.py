"""Deterministic AI v2 contract/privacy release gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .boundary import assert_ai_v2_boundary

ROOT = Path(__file__).resolve().parents[3]


def run_gate() -> list[tuple[str, int]]:
    commands = [
        ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_ai_v2_*.py", "-q"], "v2-contract"),
        ([sys.executable, "-m", "compileall", "-q", "src/creative_studio/ai_v2"], "compileall"),
        (["node", "--check", "static/ai-v2/app.js"], "node"),
        (["git", "diff", "--check"], "diff-check"),
    ]
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    results: list[tuple[str, int]] = []
    for command, name in commands:
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        results.append((name, completed.returncode))
        if completed.returncode:
            break
    try:
        assert_ai_v2_boundary(ROOT)
        results.append(("boundary", 0))
    except Exception:
        results.append(("boundary", 1))
    return results


def main() -> int:
    results = run_gate()
    for name, code in results:
        print(f"{name}: {'ok' if code == 0 else 'failed'}")
    print(json.dumps({"evidence_type": "deterministic_fake", "quality_claim": "contract_only", "real_model_quality": "not-run"}, ensure_ascii=False))
    return 0 if all(code == 0 for _, code in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

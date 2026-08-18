from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> dict:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return {
        "command": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout[-12000:],
        "stderr": p.stderr[-12000:],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="BLACK Pokemon Championship execution gate")
    ap.add_argument("--cg-dir", required=True)
    ap.add_argument("--out", default="artifacts/competition_exec.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    result = {"status": "started", "root": str(root), "steps": []}

    result["steps"].append(run([sys.executable, "scripts/static_gate.py"], root))

    if result["steps"][-1]["returncode"] != 0:
        result["status"] = "gate_failed"
    else:
        result["status"] = "ready"

    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

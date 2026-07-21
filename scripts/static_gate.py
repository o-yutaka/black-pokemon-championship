from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from submission_contract import REQUIRED_CG_FILES, validate_runtime_layout, validate_source_layout

    source = validate_source_layout(ROOT)
    with tempfile.TemporaryDirectory(prefix="dragapult_submission_gate_") as raw:
        staged = Path(raw)
        for name in ("main.py", "deck.csv", "submission_contract.py"):
            shutil.copy2(ROOT / name, staged / name)
        shutil.copytree(ROOT / "black_engine", staged / "black_engine")
        cg = staged / "cg"
        cg.mkdir()
        for name in REQUIRED_CG_FILES:
            (cg / name).write_bytes(b"x" if name == "libcg.so" else b"")
        runtime = validate_runtime_layout(staged)
        code = f"import sys,json; sys.path.insert(0,{str(staged)!r}); import main; print(json.dumps({{'deck':main.agent(None,None),'module':main.__file__}}))"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(staged)
        process = subprocess.run([sys.executable, "-I", "-c", code], cwd=staged, env=env, capture_output=True, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"isolated submission import failed: {process.stderr}")
        payload = json.loads(process.stdout.strip().splitlines()[-1])
        if len(payload.get("deck", [])) != 60:
            raise RuntimeError("deck handshake failed")
        if Path(payload["module"]).resolve() != (staged / "main.py").resolve():
            raise RuntimeError("wrong main.py imported")
    print(json.dumps({"verdict": "STATIC_GATE_PASS", "source": source, "runtime": runtime}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

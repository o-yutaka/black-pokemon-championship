from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path


def load_agent(root: Path):
    os.environ["BLACK_BUNDLE_ROOT"] = str(root)
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("black_uploaded_agent_main", root / "main.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bundle main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent = getattr(module, "agent", None)
    if not callable(agent):
        raise RuntimeError("bundle main.py must export callable agent")
    return agent


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    try:
        agent = load_agent(root)
    except Exception as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc(limit=5)}), flush=True)
        return 2
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = agent(request.get("observation"), request.get("configuration"))
            print(json.dumps({"ok": True, "selection": result}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

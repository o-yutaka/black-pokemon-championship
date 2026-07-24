from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

WORKER_DIRECTORY = Path(__file__).resolve().parent
if str(WORKER_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(WORKER_DIRECTORY))

from decision_overlay import json_safe, split_agent_result


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
    return module, agent


def _call_overlay_hook(hook: Any, observation: Any, selection: Any) -> Any:
    try:
        return hook()
    except TypeError:
        return hook(observation, selection)


def collect_overlay(module: Any, agent: Any, observation: Any, selection: Any, explicit: dict[str, Any] | None) -> dict[str, Any] | None:
    if explicit:
        return json_safe(explicit)

    for owner, name in (
        (agent, "get_black_decision_overlay"),
        (module, "get_black_decision_overlay"),
        (agent, "black_decision_overlay"),
    ):
        hook = getattr(owner, name, None)
        if callable(hook):
            value = _call_overlay_hook(hook, observation, selection)
            if isinstance(value, dict):
                return json_safe(value)

    for owner, name in (
        (agent, "BLACK_DECISION_OVERLAY"),
        (module, "BLACK_DECISION_OVERLAY"),
        (agent, "last_decision_overlay"),
        (module, "last_decision_overlay"),
    ):
        value = getattr(owner, name, None)
        if isinstance(value, dict):
            if name == "BLACK_DECISION_OVERLAY":
                try:
                    setattr(owner, name, None)
                except (AttributeError, TypeError):
                    pass
            return json_safe(value)
    return None


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    try:
        module, agent = load_agent(root)
    except Exception as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc(limit=5)}), flush=True)
        return 2
    print(json.dumps({"ready": True, "overlayProtocol": "1.0"}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            observation = request.get("observation")
            result = agent(observation, request.get("configuration"))
            selection, explicit_overlay = split_agent_result(result)
            overlay = collect_overlay(module, agent, observation, selection, explicit_overlay)
            print(json.dumps({"ok": True, "selection": json_safe(selection), "overlay": overlay}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

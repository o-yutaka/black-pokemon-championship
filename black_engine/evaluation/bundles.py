from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class LoadedBundle:
    root: Path
    agent: Callable[[dict, Any], list[int]]
    deck: list[int]
    sha256: str


def tree_sha256(root: Path) -> str:
    root = root.resolve()
    digest = hashlib.sha256()
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _purge_bundle_modules() -> None:
    for name in list(sys.modules):
        if name == "submission_contract" or name == "black_engine" or name.startswith("black_engine."):
            sys.modules.pop(name, None)


def load_bundle(root: str | Path) -> LoadedBundle:
    bundle = Path(root).resolve()
    required = (bundle / "main.py", bundle / "deck.csv", bundle / "submission_contract.py")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"bundle missing required files: {missing}")

    code = (bundle / "main.py").read_text(encoding="utf-8")
    old_cwd = Path.cwd()
    old_path = list(sys.path)
    old_root = os.environ.get("BLACK_BUNDLE_ROOT")
    _purge_bundle_modules()
    try:
        os.environ["BLACK_BUNDLE_ROOT"] = str(bundle)
        os.chdir(bundle)
        sys.path[:] = [str(bundle), *old_path]
        namespace: dict[str, Any] = {
            "__name__": f"black_bundle_{tree_sha256(bundle)[:12]}",
            "__builtins__": __builtins__,
        }
        exec(compile(code, str(bundle / "main.py"), "exec"), namespace)
        agent = namespace.get("agent")
        if not callable(agent):
            raise RuntimeError("bundle main.py did not expose callable agent")
        deck = agent({"current": None, "select": None, "logs": [], "step": 0}, None)
        if not isinstance(deck, list) or len(deck) != 60 or any(type(value) is not int for value in deck):
            raise RuntimeError("bundle agent did not return an exact 60-card integer deck")
        return LoadedBundle(bundle, agent, list(deck), tree_sha256(bundle))
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path
        if old_root is None:
            os.environ.pop("BLACK_BUNDLE_ROOT", None)
        else:
            os.environ["BLACK_BUNDLE_ROOT"] = old_root
        _purge_bundle_modules()

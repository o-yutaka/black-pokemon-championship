from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidate_roots() -> list[Path]:
    """Return portable bundle-root candidates without assuming ``__file__`` exists."""
    candidates: list[Path] = [Path.cwd()]

    explicit = os.environ.get("BLACK_BUNDLE_ROOT")
    if explicit:
        candidates.insert(0, Path(explicit))

    # Kaggle CABT evaluates raw Python with exec(code_object, env), so __file__
    # may be absent. Reading it through globals() is optional compatibility only.
    module_file = globals().get("__file__")
    if isinstance(module_file, str) and module_file:
        candidates.append(Path(module_file).resolve().parent)

    # Reuse import roots supplied by the runtime instead of hard-coding Kaggle
    # or local absolute paths.
    for entry in sys.path:
        if isinstance(entry, str) and entry:
            candidates.append(Path(entry))

    return candidates


def _find_bundle_root() -> Path:
    seen: set[Path] = set()
    for candidate in _candidate_roots():
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / name).is_file() for name in ("main.py", "deck.csv", "submission_contract.py")):
            return candidate

    raise RuntimeError(
        "submission bundle root not found; checked: "
        + ", ".join(str(path) for path in seen)
    )


ROOT = _find_bundle_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from submission_contract import validate_runtime_layout

validate_runtime_layout(ROOT)

from black_engine import DragapultPolicy, SubmissionRuntime, read_deck

DECK = read_deck(ROOT / "deck.csv")
POLICY = DragapultPolicy()
RUNTIME = SubmissionRuntime(
    POLICY,
    DECK,
    budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")),
)


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)


def get_black_decision_overlay():
    """Local Battle Studio side-channel; ignored by Kaggle submission runtime."""
    return RUNTIME.get_decision_overlay()

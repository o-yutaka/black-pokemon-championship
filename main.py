from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_bundle_root() -> Path:
    candidates: list[Path] = []
    explicit = os.environ.get("BLACK_BUNDLE_ROOT")
    if explicit:
        candidates.append(Path(explicit))

    module_file = globals().get("__file__")
    if isinstance(module_file, str) and module_file:
        candidates.append(Path(module_file).resolve().parent)

    candidates.extend((Path("/kaggle_simulations/agent"), Path.cwd()))

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
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

from black_engine import ChampionshipRocketMewtwoPolicy, SubmissionRuntime, read_deck

DECK = read_deck(ROOT / "deck.csv")
POLICY = ChampionshipRocketMewtwoPolicy()
RUNTIME = SubmissionRuntime(
    POLICY,
    DECK,
    budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")),
)


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)

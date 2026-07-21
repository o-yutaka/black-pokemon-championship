from __future__ import annotations

import sys
from pathlib import Path


def _resolve_root() -> tuple[Path, Path]:
    source_file = globals().get("__file__")
    source_dir = Path(source_file).resolve().parent if source_file else None
    candidates = []
    if source_dir is not None:
        candidates.append(source_dir.parents[1])
    candidates.extend((Path.cwd().resolve(), Path("/kaggle_simulations/agent")))
    for root in candidates:
        if (root / "black_engine").is_dir() and (root / "black_lab.py").is_file():
            deck_path = source_dir / "deck.csv" if source_dir and (source_dir / "deck.csv").is_file() else root / "deck.csv"
            if deck_path.is_file():
                return root, deck_path
    raise RuntimeError("Mewtwo v2.1 root not found")


ROOT, DECK_PATH = _resolve_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine import build_candidate_base_policy, build_hybrid_policy
from black_lab import read_deck

CANDIDATE = "mewtwo_spidops_v2_1_xerosic"
BASE_POLICY = build_candidate_base_policy(CANDIDATE)
POLICY = build_hybrid_policy(CANDIDATE, BASE_POLICY, root=ROOT)
DECK = read_deck(DECK_PATH)
POLICY.set_deck(DECK)


def agent(obs, configuration=None):
    return POLICY.agent(obs, configuration)

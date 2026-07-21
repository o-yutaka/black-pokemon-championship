from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine import build_candidate_base_policy, build_hybrid_policy
from black_lab import read_deck

BASE_POLICY = build_candidate_base_policy("crustle_redteam")
POLICY = build_hybrid_policy("crustle_redteam", BASE_POLICY, root=ROOT)
DECK = read_deck(Path(__file__).with_name("deck.csv"))
POLICY.set_deck(DECK)


def agent(obs, configuration=None):
    return POLICY.agent(obs, configuration)

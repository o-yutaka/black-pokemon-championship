from __future__ import annotations

import os

from submission_contract import CANDIDATE, require_runtime_layout

ROOT = require_runtime_layout(globals().get("__file__"))

from black_engine.factory import build_candidate_base_policy, build_hybrid_policy
from black_engine.submission_runtime import OfficialHybridRuntime
from black_lab import read_deck

DECK = read_deck(ROOT / "deck.csv")
BASE_POLICY = build_candidate_base_policy(CANDIDATE)
HYBRID_POLICY = build_hybrid_policy(CANDIDATE, BASE_POLICY, root=ROOT)
RUNTIME = OfficialHybridRuntime(
    HYBRID_POLICY,
    BASE_POLICY,
    DECK,
    budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")),
)


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)

from __future__ import annotations

import os

from submission_contract import require_runtime_layout

ROOT = require_runtime_layout(globals().get("__file__"))

from black_engine import DragapultPolicy, SubmissionRuntime, read_deck

DECK = read_deck(ROOT / "deck.csv")
POLICY = DragapultPolicy()
RUNTIME = SubmissionRuntime(POLICY, DECK, budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")))


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)

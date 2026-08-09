from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .decision_point import DecisionPoint, build_decision_points
from .hros_search_adapter import HROSSearchAdapter
from .support import legalize_selection if False else normalize_selection


@dataclass(frozen=True)
class AuthorityResult:
    selection: list[int]
    decision_points: list[DecisionPoint]
    source: str
    hros_verified: bool = False


class DecisionAuthority:
    """Single policy-facing decision boundary for every engine select window.

    The existing DragapultPolicy remains the canonical policy. This layer does
    not invent actions or bypass the runtime legality gate. HROS promotion is
    opt-in so the production submission remains behavior-compatible until the
    external verifier is proven against the official engine.
    """

    def __init__(self, policy: Any) -> None:
        self.policy = policy
        verifier = getattr(policy, "get_hros_verifier", None)
        self.hros = HROSSearchAdapter(verifier() if callable(verifier) else None)
        self.last_points: list[DecisionPoint] = []
        self.last_hros_verified = False

    def decide(self, obs: dict, configuration: Any = None) -> AuthorityResult:
        self.last_points = build_decision_points(obs)
        self.last_hros_verified = False
        selection = self.policy.agent(obs, configuration)
        selection = normalize_selection(obs, selection)

        # HROS is an external verifier. It may propose a legal alternative only
        # when explicitly enabled; otherwise it remains evidence-only.
        if self.hros.available and os.environ.get("BLACK_ENABLE_HROS_PROMOTION") == "1":
            indexes = [point.option_index for point in self.last_points]
            evidence = self.hros.verify(obs, indexes)
            if isinstance(evidence, dict):
                recommended = evidence.get("recommended")
                if isinstance(recommended, list) and recommended:
                    proposed = normalize_selection(obs, recommended)
                    if proposed == recommended:
                        selection = proposed
                        self.last_hros_verified = True

        return AuthorityResult(
            selection=selection,
            decision_points=list(self.last_points),
            source="hros_verified_policy" if self.last_hros_verified else "canonical_policy",
            hros_verified=self.last_hros_verified,
        )

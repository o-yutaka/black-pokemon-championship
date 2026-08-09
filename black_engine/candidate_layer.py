from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .decision_point import DecisionPoint, build_decision_points
from .hros_search_adapter import HROSSearchAdapter


@dataclass(frozen=True)
class CandidateScore:
    point: DecisionPoint
    score: float
    source: str = "policy"
    verified: bool = False


@dataclass(frozen=True)
class CandidateDecision:
    selection: list[int]
    candidates: list[CandidateScore]
    search_used: bool


class CandidateLayer:
    """Candidate generation only; final legality stays with SubmissionRuntime."""

    HIGH_IMPACT_TYPES = {8, 9, 10, 12, 13, 14}

    def __init__(self, policy: Any, search_adapter: HROSSearchAdapter | None = None) -> None:
        self.policy = policy
        self.search_adapter = search_adapter or HROSSearchAdapter()

    def _policy_score(self, point: DecisionPoint, obs: dict[str, Any]) -> float:
        scorer = getattr(self.policy, "score_option", None)
        if callable(scorer):
            context_builder = getattr(self.policy, "build_context", None)
            context = context_builder(obs) if callable(context_builder) else obs
            return float(scorer(point.option, context))
        # Existing canonical policies own their final action. Returning a neutral
        # score here keeps this layer observational until an explicit scorer exists.
        return 0.0

    def _needs_search(self, candidates: list[CandidateScore]) -> bool:
        if not self.search_adapter.available or len(candidates) < 2:
            return False
        ranked = sorted(candidates, key=lambda c: (c.score, -c.point.option_index), reverse=True)
        margin = ranked[0].score - ranked[1].score
        high_impact = any(c.point.action_type in self.HIGH_IMPACT_TYPES for c in ranked[:2])
        return high_impact or margin <= 0.0

    def build(self, obs: dict[str, Any]) -> CandidateDecision:
        points = build_decision_points(obs)
        if not points:
            return CandidateDecision([], [], False)

        candidates = [CandidateScore(point=p, score=self._policy_score(p, obs)) for p in points]
        search_used = False
        if self._needs_search(candidates):
            indexes = [c.point.option_index for c in sorted(candidates, key=lambda c: (c.score, -c.point.option_index), reverse=True)[:5]]
            evidence = self.search_adapter.verify(obs, indexes)
            if isinstance(evidence, dict):
                scores = evidence.get("scores")
                if isinstance(scores, dict):
                    candidates = [
                        CandidateScore(
                            point=c.point,
                            score=float(scores.get(str(c.point.option_index), c.score)),
                            source="official_search",
                            verified=str(c.point.option_index) in scores,
                        )
                        for c in candidates
                    ]
                    search_used = True

        # Preserve current option positions. No invented option is produced.
        candidates.sort(key=lambda c: (-c.score, c.point.option_index))
        select = obs.get("select") or {}
        minimum = int(select.get("minCount", 1) or 0)
        maximum_raw = select.get("maxCount", minimum)
        maximum = minimum if maximum_raw is None else int(maximum_raw or 0)
        if minimum == maximum == 1:
            selection = [candidates[0].point.option_index]
        else:
            selection = [c.point.option_index for c in candidates[:maximum]]
            if len(selection) < minimum:
                selection = [c.point.option_index for c in candidates[:minimum]]
        return CandidateDecision(selection, candidates, search_used)

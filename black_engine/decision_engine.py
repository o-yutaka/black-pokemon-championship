from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class DecisionPoint:
    option_index: int
    action_type: int | None
    card_id: int | None = None
    target_id: int | None = None
    attack_id: int | None = None
    player_index: int | None = None
    semantic: str = "unknown"


@dataclass(frozen=True)
class Candidate:
    point: DecisionPoint
    score: float
    reason: str = "policy"
    official_verified: bool = False
    opponent_checked: bool = False


@dataclass
class DecisionResult:
    selection: list[int]
    candidates: list[Candidate] = field(default_factory=list)
    searched: bool = False
    authority: str = "DecisionEngine"


class DecisionEngine:
    """Single decision authority for every engine-provided select window.

    Candidate generation remains policy-owned. This layer owns the final choice,
    confidence/impact gating, and optional official-transition/opponent hooks.
    It never invents an option that is absent from the current select window.
    """

    HIGH_IMPACT_TYPES = {8, 9, 10, 12, 13, 14}  # Energy/Evolve/Ability/Retreat/Attack/End

    def __init__(
        self,
        policy: Any,
        *,
        official_search: Callable[[dict[str, Any], list[int]], Any] | None = None,
        opponent_response: Callable[[Any], Any] | None = None,
    ) -> None:
        self.policy = policy
        self.official_search = official_search
        self.opponent_response = opponent_response
        self.last_result: DecisionResult | None = None

    @staticmethod
    def _card_id(option: dict[str, Any]) -> int | None:
        for key in ("card", "cardId", "id"):
            value = option.get(key)
            if type(value) is int:
                return value
        return None

    @staticmethod
    def _target_id(option: dict[str, Any]) -> int | None:
        for key in ("target", "pokemon", "to", "selectPokemon"):
            value = option.get(key)
            if type(value) is int:
                return value
        return None

    @classmethod
    def decision_points(cls, obs: dict[str, Any]) -> list[DecisionPoint]:
        select = obs.get("select") if isinstance(obs, dict) else None
        options = select.get("option") if isinstance(select, dict) else None
        if not isinstance(options, list):
            return []
        points: list[DecisionPoint] = []
        for index, option in enumerate(options):
            if not isinstance(option, dict):
                points.append(DecisionPoint(index, None, semantic="unknown"))
                continue
            kind = option.get("type")
            kind = kind if type(kind) is int else None
            points.append(
                DecisionPoint(
                    option_index=index,
                    action_type=kind,
                    card_id=cls._card_id(option),
                    target_id=cls._target_id(option),
                    attack_id=option.get("attackId") if type(option.get("attackId")) is int else None,
                    player_index=option.get("playerIndex") if type(option.get("playerIndex")) is int else None,
                    semantic=f"type:{kind}",
                )
            )
        return points

    def _score(self, obs: dict[str, Any], points: Iterable[DecisionPoint]) -> list[Candidate]:
        select = obs.get("select") or {}
        options = select.get("option") or []
        context = self.policy.build_context(obs)
        candidates: list[Candidate] = []
        for point in points:
            option = options[point.option_index]
            score = float(self.policy.score_option(option, context)) if isinstance(option, dict) else -1e9
            candidates.append(Candidate(point=point, score=score))
        return candidates

    def _needs_search(self, candidates: list[Candidate]) -> bool:
        if len(candidates) <= 1:
            return False
        ranked = sorted(candidates, key=lambda c: (c.score, c.point.option_index), reverse=True)
        margin = ranked[0].score - ranked[1].score
        high_impact = any(c.point.action_type in self.HIGH_IMPACT_TYPES for c in ranked[:2])
        return high_impact or margin <= 150.0

    def evaluate(self, obs: dict[str, Any]) -> DecisionResult:
        points = self.decision_points(obs)
        if not points:
            result = DecisionResult(selection=[])
            self.last_result = result
            return result

        candidates = self._score(obs, points)
        searched = False
        if self.official_search is not None and self._needs_search(candidates):
            searched = True
            indexes = [c.point.option_index for c in sorted(candidates, key=lambda c: (c.score, c.point.option_index), reverse=True)[:5]]
            verified = self.official_search(obs, indexes)
            if isinstance(verified, dict):
                scores = verified.get("scores")
                if isinstance(scores, dict):
                    candidates = [Candidate(c.point, float(scores.get(str(c.point.option_index), c.score)), "official", True, c.opponent_checked) for c in candidates]
                response = verified.get("opponent_response")
                if response is not None and self.opponent_response is not None:
                    self.opponent_response(response)

        candidates.sort(key=lambda c: (c.score, c.point.option_index), reverse=True)
        select = obs.get("select") or {}
        minimum = max(0, int(select.get("minCount", 1) or 0))
        maximum_raw = select.get("maxCount", minimum)
        maximum = minimum if maximum_raw is None else max(0, int(maximum_raw or 0))
        if minimum == maximum == 1:
            selection = [candidates[0].point.option_index]
        else:
            selection = [c.point.option_index for c in candidates[:maximum]]
            if len(selection) < minimum:
                selection = [c.point.option_index for c in candidates[:minimum]]

        result = DecisionResult(selection=selection, candidates=candidates, searched=searched)
        self.last_result = result
        return result

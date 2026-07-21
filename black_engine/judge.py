from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .guards import GuardVote
from .planners import PlannerVote
from .truth import LegalOption


@dataclass(frozen=True)
class CandidateScore:
    option: LegalOption
    heuristic: float
    rl_prior: float
    search_value: float
    search_visits: int
    belief_confidence: float
    guard_votes: tuple[GuardVote, ...]
    planner_votes: tuple[PlannerVote, ...] = ()

    @property
    def hard_rejected(self) -> bool:
        return any(vote.hard_reject for vote in self.guard_votes)

    @property
    def total(self) -> float:
        if self.hard_rejected:
            return float("-inf")
        guard_adjustment = sum(vote.bonus - vote.penalty for vote in self.guard_votes)
        planner_adjustment = sum(vote.bonus - vote.penalty for vote in self.planner_votes)
        search_weight = min(1.0, self.search_visits / 24.0)
        uncertainty_discount = 0.65 + 0.35 * max(0.0, min(1.0, self.belief_confidence))
        return (
            self.heuristic
            + 140.0 * self.rl_prior
            + 500.0 * self.search_value * search_weight * uncertainty_discount
            + guard_adjustment
            + planner_adjustment
        )


@dataclass(frozen=True)
class JudgeVerdict:
    selected_index: int
    scores: tuple[CandidateScore, ...]
    fallback_used: bool
    reason: str


class HybridJudge:
    def decide(self, scores: Iterable[CandidateScore]) -> JudgeVerdict:
        values = tuple(scores)
        legal = [value for value in values if not value.hard_rejected]
        if legal:
            # Tie-break must match ScoredPolicy.choose_single (black_lab.py):
            # max() over (score, index) maximizes index on ties. A prior
            # version negated the index here, silently reversing tie-break
            # direction versus the base policy -- with the coarse, heavily
            # bucketed scores these heuristics return, ties are common, and
            # that mismatch alone produced a spurious ~10-20pt "hybrid edge"
            # in evaluation even with every hybrid subsystem neutralized.
            selected = max(legal, key=lambda value: (value.total, value.option.index))
            return JudgeVerdict(selected.option.index, values, False, "hybrid_max_total")
        if not values:
            return JudgeVerdict(0, (), True, "no_options")
        selected = max(values, key=lambda value: (value.heuristic, value.option.index))
        return JudgeVerdict(selected.option.index, values, True, "all_guard_rejected_fallback")

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from black_lab import normalize_selection

from .belief import BayesianBeliefModel
from .guards import guards_for
from .ismcts import ISMCTSResult, InformationSetMCTS
from .judge import CandidateScore, HybridJudge
from .planners import planners_for
from .rl_prior import TabularQPrior
from .truth import build_truth_state


class HybridPolicy:
    def __init__(
        self,
        candidate: str,
        base_policy: Any,
        *,
        belief: BayesianBeliefModel | None = None,
        rl_prior: TabularQPrior | None = None,
        ismcts: InformationSetMCTS | None = None,
        trace_path: str | Path | None = None,
    ) -> None:
        self.candidate = candidate
        self.base_policy = base_policy
        self.belief = belief or BayesianBeliefModel()
        self.rl_prior = rl_prior or TabularQPrior()
        self.ismcts = ismcts
        self.guards = guards_for(candidate)
        self.planners = planners_for(candidate)
        self.judge = HybridJudge()
        self.deck: list[int] = []
        configured = trace_path or os.environ.get("BLACK_DECISION_TRACE")
        self.trace_path = Path(configured) if configured else None

    def set_deck(self, ids: list[int]) -> None:
        self.deck = [int(value) for value in ids]
        if hasattr(self.base_policy, "set_deck"):
            self.base_policy.set_deck(self.deck)

    def _trace(self, payload: dict) -> None:
        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def agent(self, obs: dict | None, configuration=None):
        if obs is None or not isinstance(obs, dict) or obs.get("select") is None:
            return list(self.deck)
        truth = build_truth_state(obs)
        if not truth.options:
            return [] if truth.min_count == 0 else list(self.deck)
        if truth.min_count != 1 or truth.max_count != 1:
            return normalize_selection(obs, self.base_policy.agent(obs, configuration))

        context = self.base_policy.build_context(obs)
        belief_snapshot = self.belief.update(truth)
        search_result = (
            self.ismcts.evaluate(truth, your_full_deck=self.deck)
            if self.ismcts is not None
            else ISMCTSResult((), 0, 0.0, False, "search adapter not connected")
        )
        scores: list[CandidateScore] = []
        for option in truth.options:
            heuristic = float(self.base_policy.score_option(option.raw, context))
            rl_score = self.rl_prior.score(truth, option)
            search = search_result.value_for(option.index)
            guard_votes = tuple(guard.evaluate(truth, option) for guard in self.guards)
            planner_votes = tuple(planner.evaluate(truth, option) for planner in self.planners)
            scores.append(CandidateScore(
                option=option,
                heuristic=heuristic,
                rl_prior=rl_score.value,
                search_value=search.mean_value,
                search_visits=search.visits,
                belief_confidence=belief_snapshot.confidence,
                guard_votes=guard_votes,
                planner_votes=planner_votes,
            ))
        verdict = self.judge.decide(scores)
        self._trace({
            "candidate": self.candidate,
            "selected_index": verdict.selected_index,
            "reason": verdict.reason,
            "fallback_used": verdict.fallback_used,
            "belief": dict(belief_snapshot.posterior),
            "belief_enabled": belief_snapshot.enabled,
            "search": {
                "enabled": search_result.enabled,
                "simulations": search_result.simulations,
                "elapsed_ms": search_result.elapsed_ms,
                "reason": search_result.reason,
            },
            "scores": [{
                "index": score.option.index,
                "signature": score.option.signature,
                "heuristic": score.heuristic,
                "rl_prior": score.rl_prior,
                "search_value": score.search_value,
                "search_visits": score.search_visits,
                "hard_rejected": score.hard_rejected,
                "total": score.total,
                "guards": [vote.__dict__ for vote in score.guard_votes],
                "planners": [vote.__dict__ for vote in score.planner_votes],
            } for score in verdict.scores],
        })
        return normalize_selection(obs, verdict.selected_index)

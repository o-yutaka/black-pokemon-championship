from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from black_lab import normalize_selection

from .belief import BayesianBeliefModel
from .dragapult_complete_guards import championship_dragapult_guards
from .guards import guards_for
from .ismcts import ISMCTSResult, InformationSetMCTS
from .judge import CandidateScore, HybridJudge
from .official_observation import normalize_official_observation
from .planners import planners_for
from .rl_prior import TabularQPrior
from .truth import build_truth_state

CANDIDATE = "dragapult_cinderace"


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
        if candidate != CANDIDATE:
            raise ValueError(f"single-deck runtime locked to {CANDIDATE}; requested={candidate}")
        self.candidate = CANDIDATE
        self.base_policy = base_policy
        self.belief = belief or BayesianBeliefModel()
        self.rl_prior = rl_prior or TabularQPrior()
        self.ismcts = ismcts
        self.guards = () if os.environ.get("BLACK_ABLATE_GUARDS") in {"1", "true", "True"} else guards_for(CANDIDATE) + championship_dragapult_guards()
        if os.environ.get("BLACK_ABLATE_BAYES") in {"1", "true", "True"}:
            self.belief = BayesianBeliefModel()
        if os.environ.get("BLACK_ABLATE_RL") in {"1", "true", "True"}:
            self.rl_prior = TabularQPrior()
        if os.environ.get("BLACK_ABLATE_ISMCTS") in {"1", "true", "True"}:
            self.ismcts = None
        self.planners = planners_for(CANDIDATE)
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
        truth = build_truth_state(normalize_official_observation(obs))
        if not truth.options:
            return []
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
            scores.append(CandidateScore(
                option=option,
                heuristic=float(self.base_policy.score_option(option.raw, context)),
                rl_prior=self.rl_prior.score(truth, option).value,
                search_value=search_result.value_for(option.index).mean_value,
                search_visits=search_result.value_for(option.index).visits,
                belief_confidence=belief_snapshot.confidence,
                guard_votes=tuple(guard.evaluate(truth, option) for guard in self.guards),
                planner_votes=tuple(planner.evaluate(truth, option) for planner in self.planners),
            ))
        verdict = self.judge.decide(scores)
        self._trace({
            "candidate": CANDIDATE,
            "selected_index": verdict.selected_index,
            "reason": verdict.reason,
            "fallback_used": verdict.fallback_used,
            "belief": dict(belief_snapshot.posterior),
            "search": {
                "enabled": search_result.enabled,
                "simulations": search_result.simulations,
                "elapsed_ms": search_result.elapsed_ms,
                "reason": search_result.reason,
            },
        })
        return normalize_selection(obs, verdict.selected_index)

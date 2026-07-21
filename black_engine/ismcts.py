from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Protocol

from .belief import BayesianBeliefModel, Determinization
from .truth import TruthState, build_truth_state


@dataclass(frozen=True)
class SearchFrame:
    search_id: int
    observation: dict
    terminal_result: int = -1


class SearchAdapter(Protocol):
    def begin(self, truth: TruthState, determinization: Determinization) -> SearchFrame: ...
    def step(self, search_id: int, selection: list[int]) -> SearchFrame: ...
    def release(self, search_id: int) -> None: ...
    def end(self) -> None: ...


@dataclass
class _ActionStat:
    visits: int = 0
    value_sum: float = 0.0

    @property
    def mean(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass(frozen=True)
class RootActionValue:
    index: int
    visits: int
    mean_value: float


@dataclass(frozen=True)
class ISMCTSResult:
    actions: tuple[RootActionValue, ...]
    simulations: int
    elapsed_ms: float
    enabled: bool
    reason: str = ""

    def value_for(self, index: int) -> RootActionValue:
        return next((value for value in self.actions if value.index == index), RootActionValue(index, 0, 0.0))


class InformationSetMCTS:
    """Root-parallel SO-ISMCTS over CABT Search states.

    Each simulation samples a hidden-state determinization from the Bayesian
    belief. Tree decisions use only observations returned by SearchStep.
    """

    def __init__(
        self,
        adapter: SearchAdapter,
        belief: BayesianBeliefModel,
        *,
        simulations: int = 48,
        time_budget_ms: float = 35.0,
        exploration: float = 1.2,
        rollout_depth: int = 8,
        seed: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.belief = belief
        self.simulations = max(1, int(simulations))
        self.time_budget_ms = max(1.0, float(time_budget_ms))
        self.exploration = max(0.0, float(exploration))
        self.rollout_depth = max(1, int(rollout_depth))
        self.rng = random.Random(seed)

    @staticmethod
    def _terminal_reward(result: int, root_actor: int) -> float:
        if result not in (0, 1):
            return 0.0
        return 1.0 if result == root_actor else -1.0

    @staticmethod
    def _state_heuristic(truth: TruthState, root_actor: int) -> float:
        me = truth.players[root_actor]
        opponent = truth.players[1 - root_actor]
        my_hp = sum(p.remaining_hp for p in me.in_play)
        opp_hp = sum(p.remaining_hp for p in opponent.in_play)
        my_energy = sum(p.energy_count for p in me.in_play)
        opp_energy = sum(p.energy_count for p in opponent.in_play)
        board = 0.002 * (my_hp - opp_hp) + 0.05 * (my_energy - opp_energy)
        hand = 0.02 * (me.hand_count - opponent.hand_count)
        return max(-0.9, min(0.9, board + hand))

    def _choose_root(self, stats: dict[int, _ActionStat], total_visits: int) -> int:
        unvisited = [index for index, stat in stats.items() if stat.visits == 0]
        if unvisited:
            return self.rng.choice(unvisited)
        log_total = math.log(max(1, total_visits))
        return max(
            stats,
            key=lambda index: stats[index].mean
            + self.exploration * math.sqrt(log_total / stats[index].visits),
        )

    def _rollout(self, frame: SearchFrame, root_actor: int) -> float:
        current = frame
        allocated: list[int] = [current.search_id]
        try:
            for _ in range(self.rollout_depth):
                if current.terminal_result in (0, 1):
                    return self._terminal_reward(current.terminal_result, root_actor)
                truth = build_truth_state(current.observation)
                if truth.terminal:
                    return self._terminal_reward(truth.result, root_actor)
                if not truth.options:
                    return self._state_heuristic(truth, root_actor)
                ranked = sorted(
                    truth.options,
                    key=lambda option: (
                        option.action_type in (13, 9, 10, 8),
                        option.action_type != 14,
                        -option.index,
                    ),
                    reverse=True,
                )
                option = ranked[0] if self.rng.random() > 0.15 else self.rng.choice(list(truth.options))
                current = self.adapter.step(current.search_id, [option.index])
                allocated.append(current.search_id)
            return self._state_heuristic(build_truth_state(current.observation), root_actor)
        finally:
            for search_id in reversed(allocated):
                try:
                    self.adapter.release(search_id)
                except Exception:
                    pass

    def evaluate(self, truth: TruthState, *, your_full_deck: list[int]) -> ISMCTSResult:
        if truth.min_count != 1 or truth.max_count != 1 or not truth.options:
            return ISMCTSResult((), 0, 0.0, False, "ISMCTS supports root single-select only")
        snapshot = self.belief.update(truth)
        if not snapshot.enabled:
            return ISMCTSResult((), 0, 0.0, False, snapshot.reason)
        stats = {option.index: _ActionStat() for option in truth.options}
        start = time.perf_counter()
        completed = 0
        try:
            while completed < self.simulations:
                if (time.perf_counter() - start) * 1000.0 >= self.time_budget_ms:
                    break
                determinization = self.belief.sample_hidden(truth, your_full_deck=your_full_deck, rng=self.rng)
                root = self.adapter.begin(truth, determinization)
                root_index = self._choose_root(stats, completed + 1)
                child = self.adapter.step(root.search_id, [root_index])
                try:
                    reward = self._rollout(child, truth.actor)
                finally:
                    try:
                        self.adapter.release(root.search_id)
                    except Exception:
                        pass
                stat = stats[root_index]
                stat.visits += 1
                stat.value_sum += reward
                completed += 1
        finally:
            try:
                self.adapter.end()
            except Exception:
                pass
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ISMCTSResult(
            tuple(RootActionValue(index, stat.visits, stat.mean) for index, stat in sorted(stats.items())),
            completed,
            elapsed_ms,
            True,
        )

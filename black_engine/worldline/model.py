from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlanStep:
    name: str
    expected_context: int | None = None
    expected_type: int | None = None
    card_id: int | None = None
    target_serial: int | None = None


@dataclass
class CandidatePlan:
    plan_id: str
    goal: str
    root_action_index: int
    steps: tuple[PlanStep, ...] = ()
    reserved_serials: tuple[int, ...] = ()
    reserved_card_ids: tuple[int, ...] = ()
    abort_conditions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass
class WorldlineResult:
    plan: CandidatePlan
    illegal: bool = False
    immediate_loss: bool = False
    guaranteed_win: bool = False
    prevents_forced_loss: bool = False
    our_attacks_to_win: int = 99
    opponent_attacks_to_win: int = 0
    hostile_survival: float = 0.0
    irreversible_cost: float = 0.0
    opponent_pain: float = 0.0
    regret: float = 0.0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingPlan:
    candidate: CandidatePlan
    current_step: int = 0
    status: str = "RUNNING"
    bindings: dict[str, int] = field(default_factory=dict)

    @property
    def step(self) -> PlanStep | None:
        if self.status != "RUNNING" or self.current_step >= len(self.candidate.steps):
            return None
        return self.candidate.steps[self.current_step]

    def advance(self) -> None:
        self.current_step += 1
        if self.current_step >= len(self.candidate.steps):
            self.status = "COMPLETE"

    def abort(self, reason: str) -> None:
        self.status = f"ABORTED:{reason}"

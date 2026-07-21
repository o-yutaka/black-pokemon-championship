from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .truth import LegalOption, TruthState

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
MEWTWO_EX, SPIDOPS, WOBBUFFET = 431, 401, 432
ROCKET_POKEMON = {400, 401, 414, 431, 432, 463}
GARCHOMP_EX, SPIRITOMB, ROSERADE, GABITE = 381, 387, 342, 380
CYNTHIA_POKEMON = {341, 342, 379, 380, 381, 387}


@dataclass(frozen=True)
class PlannerVote:
    planner: str
    bonus: float = 0.0
    penalty: float = 0.0
    reason: str = ""


class Planner(Protocol):
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote: ...


def _active_id(truth: TruthState) -> int:
    return truth.me.active[0].card_id if truth.me.active else -1


def _remaining(truth: TruthState) -> int:
    return truth.opponent.active[0].remaining_hp if truth.opponent.active else 0


class TerminalPlanner:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        remaining = _remaining(truth)
        if not remaining:
            return PlannerVote("terminal")
        if self.candidate == "mewtwo_spidops" and _active_id(truth) == MEWTWO_EX and option.action_type == T_ATTACK:
            if remaining <= 280:
                return PlannerVote("terminal", bonus=180, reason="Mewtwo 160/220/280 terminal band")
        if self.candidate == "garchomp_spiritomb":
            roses = sum(p.card_id == ROSERADE for p in truth.me.in_play)
            reservoir = sum(p.damage for p in truth.me.bench if p.card_id in CYNTHIA_POKEMON)
            if _active_id(truth) == SPIRITOMB and option.action_type == T_ATTACK and reservoir + 30 * roses >= remaining:
                return PlannerVote("terminal", bonus=220, reason="Spiritomb stored-damage lethal")
            if _active_id(truth) == GARCHOMP_EX and option.action_type == T_ATTACK:
                heavy = any(token in option.label for token in ("draconic", "buster", "260"))
                light = any(token in option.label for token in ("corkscrew", "dive", "100"))
                damage = (260 if heavy else 100 if light else 0) + 30 * roses
                if damage >= remaining:
                    return PlannerVote("terminal", bonus=190, reason="Garchomp exact lethal")
        return PlannerVote("terminal")


class SetupPlanner:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        if self.candidate == "mewtwo_spidops":
            rocket_count = sum(p.card_id in ROCKET_POKEMON for p in truth.me.in_play)
            if rocket_count < 4 and option.action_type in {T_PLAY, T_EVOLVE, T_ABILITY}:
                if option.card_id in ROCKET_POKEMON or option.card_id in {1094, 1134, 1152, 1220}:
                    return PlannerVote("setup", bonus=130, reason="complete four Rocket bodies")
            if option.action_type == T_EVOLVE and option.card_id == SPIDOPS:
                return PlannerVote("setup", bonus=120, reason="activate renewable reservoir")
        else:
            has_garchomp = any(p.card_id == GARCHOMP_EX for p in truth.me.in_play)
            if not has_garchomp and option.action_type == T_EVOLVE and option.card_id in {GABITE, GARCHOMP_EX}:
                return PlannerVote("setup", bonus=150, reason="establish Garchomp draw loop")
            if option.action_type == T_EVOLVE and option.card_id == ROSERADE:
                return PlannerVote("setup", bonus=100, reason="increase Cynthia damage scaling")
        return PlannerVote("setup")


class ResourcePlanner:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        if self.candidate == "mewtwo_spidops":
            reservoir = sum(p.energy_count for p in truth.me.bench)
            if option.action_type == T_ENERGY and option.target_id == SPIDOPS and reservoir < 2:
                return PlannerVote("resource", bonus=100, reason="build Spidops reservoir")
            if option.action_type == T_ATTACK and _active_id(truth) == WOBBUFFET:
                damaged = max((p.damage for p in truth.me.bench if p.card_id in ROCKET_POKEMON), default=0)
                if damaged >= _remaining(truth) > 0:
                    return PlannerVote("resource", bonus=170, reason="convert stored damage without ex exposure")
        else:
            if option.action_type == T_ATTACK and _active_id(truth) == GARCHOMP_EX:
                if any(token in option.label for token in ("corkscrew", "dive", "100")):
                    return PlannerVote("resource", bonus=90, reason="sustainable damage plus draw-to-six")
            if option.action_type == T_ENERGY and option.target_id == SPIRITOMB:
                roses = sum(p.card_id == ROSERADE for p in truth.me.in_play)
                reservoir = sum(p.damage for p in truth.me.bench if p.card_id in CYNTHIA_POKEMON)
                if reservoir + 30 * roses >= _remaining(truth) > 0:
                    return PlannerVote("resource", bonus=140, reason="power exact Spiritomb handoff")
        return PlannerVote("resource")


def planners_for(candidate: str) -> tuple[Planner, ...]:
    if candidate not in {"mewtwo_spidops", "garchomp_spiritomb"}:
        raise ValueError(f"unknown candidate: {candidate}")
    return (TerminalPlanner(candidate), SetupPlanner(candidate), ResourcePlanner(candidate))

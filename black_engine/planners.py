from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .truth import LegalOption, TruthState

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
MEWTWO_EX, SPIDOPS, WOBBUFFET = 431, 401, 432
ROCKET_POKEMON = {400, 401, 414, 431, 432, 463}
GARCHOMP_EX, SPIRITOMB, ROSERADE, GABITE = 381, 387, 342, 380
CYNTHIA_POKEMON = {341, 342, 379, 380, 381, 387}

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR, AZELF, CINDERACE = 131, 132, 133, 217, 666
POFFIN, RARE_CANDY, TERA_ORB, POKE_PAD = 1086, 1079, 1127, 1152
CRISPIN, DAWN, LILLIE, PRIME_CATCHER, SWITCH = 1198, 1231, 1227, 1088, 1123
DRAGAPULT_JET_HEADBUTT, DRAGAPULT_PHANTOM_DIVE = 153, 154
AZELF_NEUROKINESIS, CINDERACE_TURBO_FLARE = 292, 965


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
        if self.candidate == "dragapult_cinderace":
            if _active_id(truth) == DRAGAPULT_EX and option.action_type == T_ATTACK:
                damage = 200 if option.attack_id == DRAGAPULT_PHANTOM_DIVE else 70 if option.attack_id == DRAGAPULT_JET_HEADBUTT else 0
                if damage >= remaining:
                    return PlannerVote("terminal", bonus=240, reason="Dragapult active KO")
            if _active_id(truth) == AZELF and option.action_type == T_ATTACK and option.attack_id == AZELF_NEUROKINESIS:
                effective = 10 + sum(p.damage for p in truth.opponent.in_play)
                if effective >= remaining:
                    return PlannerVote("terminal", bonus=280, reason="Azelf converts all opposing counters into lethal")
            if option.action_type == T_ABILITY and option.card_id in {DUSCLOPS, DUSKNOIR}:
                blast = 50 if option.card_id == DUSCLOPS else 130
                if any(0 < p.remaining_hp <= blast for p in truth.opponent.in_play):
                    return PlannerVote("terminal", bonus=260, reason=f"Cursed Blast closes <= {blast} HP target")
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
        elif self.candidate == "garchomp_spiritomb":
            has_garchomp = any(p.card_id == GARCHOMP_EX for p in truth.me.in_play)
            if not has_garchomp and option.action_type == T_EVOLVE and option.card_id in {GABITE, GARCHOMP_EX}:
                return PlannerVote("setup", bonus=150, reason="establish Garchomp draw loop")
            if option.action_type == T_EVOLVE and option.card_id == ROSERADE:
                return PlannerVote("setup", bonus=100, reason="increase Cynthia damage scaling")
        elif self.candidate == "dragapult_cinderace":
            has_dragapult = any(p.card_id == DRAGAPULT_EX for p in truth.me.in_play)
            has_dusknoir = any(p.card_id == DUSKNOIR for p in truth.me.in_play)
            if option.action_type == T_EVOLVE and option.card_id == DRAGAPULT_EX:
                return PlannerVote("setup", bonus=190, reason="establish Phantom Dive engine")
            if option.action_type == T_EVOLVE and option.card_id == DRAKLOAK:
                return PlannerVote("setup", bonus=150, reason="establish Recon Directive bridge")
            if option.action_type == T_EVOLVE and option.card_id in {DUSCLOPS, DUSKNOIR}:
                return PlannerVote("setup", bonus=165 if not has_dusknoir else 90, reason="prepare Cursed Blast conversion")
            if option.action_type == T_PLAY and option.card_id in {POFFIN, RARE_CANDY, TERA_ORB, POKE_PAD, DAWN}:
                return PlannerVote("setup", bonus=145 if not has_dragapult else 80, reason="role-specific Stage 2 search package")
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
        elif self.candidate == "garchomp_spiritomb":
            if option.action_type == T_ATTACK and _active_id(truth) == GARCHOMP_EX:
                if any(token in option.label for token in ("corkscrew", "dive", "100")):
                    return PlannerVote("resource", bonus=90, reason="sustainable damage plus draw-to-six")
            if option.action_type == T_ENERGY and option.target_id == SPIRITOMB:
                roses = sum(p.card_id == ROSERADE for p in truth.me.in_play)
                reservoir = sum(p.damage for p in truth.me.bench if p.card_id in CYNTHIA_POKEMON)
                if reservoir + 30 * roses >= _remaining(truth) > 0:
                    return PlannerVote("resource", bonus=140, reason="power exact Spiritomb handoff")
        elif self.candidate == "dragapult_cinderace":
            if option.action_type == T_ATTACK and _active_id(truth) == CINDERACE and option.attack_id == CINDERACE_TURBO_FLARE:
                missing = sum(max(0, 2 - p.energy_count) for p in truth.me.bench if p.card_id in {DREEPY, DRAKLOAK, DRAGAPULT_EX, AZELF})
                return PlannerVote("resource", bonus=220 if missing >= 2 else 70, reason=f"Turbo Flare future-energy value={missing}")
            if option.action_type == T_ENERGY and option.target_id in {DREEPY, DRAKLOAK, DRAGAPULT_EX}:
                return PlannerVote("resource", bonus=135, reason="fund Fire+Psychic Phantom Dive route")
            if option.action_type == T_PLAY and option.card_id == CRISPIN:
                return PlannerVote("resource", bonus=175, reason="search one color and accelerate the other")
            if option.action_type in {T_RETREAT, T_PLAY} and (_active_id(truth) == CINDERACE):
                if option.action_type == T_RETREAT or option.card_id in {SWITCH, PRIME_CATCHER}:
                    ready = any(p.card_id == DRAGAPULT_EX and p.energy_count >= 2 for p in truth.me.bench)
                    if ready:
                        return PlannerVote("resource", bonus=210, reason="Cinderace-to-Dragapult attack handoff")
        return PlannerVote("resource")


class SpreadPlanner:
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        if _active_id(truth) == DRAGAPULT_EX and option.action_type == T_ATTACK and option.attack_id == DRAGAPULT_PHANTOM_DIVE:
            bench_targets = len(truth.opponent.bench)
            return PlannerVote("spread", bonus=80 + 35 * min(3, bench_targets), reason=f"Phantom Dive bench targets={bench_targets}")
        if _active_id(truth) == AZELF and option.action_type == T_ATTACK and option.attack_id == AZELF_NEUROKINESIS:
            total = sum(p.damage for p in truth.opponent.in_play)
            return PlannerVote("spread", bonus=min(240, total), reason=f"Azelf counter reservoir={total}")
        return PlannerVote("spread")


def planners_for(candidate: str) -> tuple[Planner, ...]:
    if candidate not in {
        "mewtwo_spidops", "garchomp_spiritomb", "dragapult_cinderace",
        "crustle_redteam", "grimmsnarl_redteam",
    }:
        raise ValueError(f"unknown candidate: {candidate}")
    common: tuple[Planner, ...] = (TerminalPlanner(candidate), SetupPlanner(candidate), ResourcePlanner(candidate))
    return common + ((SpreadPlanner(),) if candidate == "dragapult_cinderace" else ())

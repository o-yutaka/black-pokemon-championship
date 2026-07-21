from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .truth import LegalOption, TruthState

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
MEWTWO_EX, SPIDOPS = 431, 401
ROCKET_POKEMON = {400, 401, 414, 431, 432, 463}
GARCHOMP_EX, SPIRITOMB, ROSERADE = 381, 387, 342
CYNTHIA_POKEMON = {341, 342, 379, 380, 381, 387}


@dataclass(frozen=True)
class GuardVote:
    guard: str
    hard_reject: bool = False
    penalty: float = 0.0
    bonus: float = 0.0
    reason: str = ""


class Guard(Protocol):
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote: ...


def _active_id(truth: TruthState) -> int:
    return truth.me.active[0].card_id if truth.me.active else -1


def _opp_remaining(truth: TruthState) -> int:
    return truth.opponent.active[0].remaining_hp if truth.opponent.active else 0


def _label_has(option: LegalOption, *tokens: str) -> bool:
    return any(token in option.label for token in tokens)


class LegalContractGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if not (0 <= option.index < len(truth.options)):
            return GuardVote("legal_contract", True, reason="option index out of range")
        return GuardVote("legal_contract")


class HiddenInformationGuard:
    _forbidden = {"opponentHand", "opponentDeck", "opponentPrize", "hiddenCard", "trueCard"}

    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        leaked = sorted(set(option.raw) & self._forbidden)
        if leaked:
            return GuardVote("hidden_information", True, reason=f"forbidden option fields: {leaked}")
        return GuardVote("hidden_information")


class MewtwoFourRocketGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ATTACK or _active_id(truth) != MEWTWO_EX:
            return GuardVote("mewtwo_four_rocket")
        rocket_count = sum(p.card_id in ROCKET_POKEMON for p in truth.me.in_play)
        if rocket_count < 4:
            return GuardVote("mewtwo_four_rocket", True, reason=f"rocket_count={rocket_count}<4")
        return GuardVote("mewtwo_four_rocket", bonus=80, reason="four Rocket bodies online")


class MewtwoEnergyFutureGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ATTACK or _active_id(truth) != MEWTWO_EX:
            return GuardVote("mewtwo_energy_future")
        reservoir = sum(p.energy_count for p in truth.me.bench)
        remaining = _opp_remaining(truth)
        needed = 0 if remaining <= 160 else 1 if remaining <= 220 else 2 if remaining <= 280 else 3
        if needed >= 2 and reservoir <= 2 and remaining > 220:
            return GuardVote(
                "mewtwo_energy_future",
                penalty=180,
                reason="attack may empty renewable reservoir without confirmed terminal",
            )
        return GuardVote("mewtwo_energy_future", bonus=40 if remaining and remaining <= 280 else 0)


class GarchompHeavyAttackGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ATTACK or _active_id(truth) != GARCHOMP_EX:
            return GuardVote("garchomp_heavy_attack")
        if not _label_has(option, "draconic", "buster", "260"):
            return GuardVote("garchomp_heavy_attack")
        roses = sum(p.card_id == ROSERADE for p in truth.me.in_play)
        damage = 260 + 30 * roses
        remaining = _opp_remaining(truth)
        active_energy = truth.me.active[0].energy_count if truth.me.active else 0
        if remaining and damage >= remaining:
            return GuardVote("garchomp_heavy_attack", bonus=120, reason="decisive KO")
        if active_energy <= 2:
            return GuardVote(
                "garchomp_heavy_attack",
                penalty=240,
                reason="nonlethal heavy attack consumes follow-up energy route",
            )
        return GuardVote("garchomp_heavy_attack", penalty=90, reason="nonlethal heavy attack")


class SpiritombTerminalGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if not truth.opponent.active:
            return GuardVote("spiritomb_terminal")
        spiritomb_present = any(p.card_id == SPIRITOMB for p in truth.me.in_play)
        if not spiritomb_present:
            return GuardVote("spiritomb_terminal")
        reservoir = sum(p.damage for p in truth.me.bench if p.card_id in CYNTHIA_POKEMON)
        roses = sum(p.card_id == ROSERADE for p in truth.me.in_play)
        lethal = reservoir + 30 * roses >= truth.opponent.active[0].remaining_hp > 0
        if not lethal:
            return GuardVote("spiritomb_terminal")
        if option.action_type == T_RETREAT or option.target_id == SPIRITOMB or (
            option.action_type == T_ATTACK and _active_id(truth) == SPIRITOMB
        ):
            return GuardVote("spiritomb_terminal", bonus=300, reason="Spiritomb exact-lethal route")
        if option.action_type == T_END:
            return GuardVote("spiritomb_terminal", True, reason="ending turn misses Spiritomb lethal")
        return GuardVote("spiritomb_terminal", penalty=120, reason="action delays available Spiritomb lethal")


class EndTurnValueGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_END:
            return GuardVote("end_turn_value")
        if any(candidate.action_type in {T_ATTACK, T_EVOLVE, T_ABILITY, T_ENERGY} for candidate in truth.options):
            return GuardVote("end_turn_value", penalty=220, reason="valuable non-END action remains")
        return GuardVote("end_turn_value")


def guards_for(candidate: str) -> tuple[Guard, ...]:
    common: tuple[Guard, ...] = (LegalContractGuard(), HiddenInformationGuard(), EndTurnValueGuard())
    if candidate == "mewtwo_spidops":
        return common + (MewtwoFourRocketGuard(), MewtwoEnergyFutureGuard())
    if candidate == "garchomp_spiritomb":
        return common + (GarchompHeavyAttackGuard(), SpiritombTerminalGuard())
    raise ValueError(f"unknown candidate: {candidate}")

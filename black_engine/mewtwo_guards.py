from __future__ import annotations

from .guards import GuardVote
from .rocket_ledger import (
    BASIC_ENERGY_IDS,
    MEWTWO_EX,
    ROCKET_POKEMON,
    SPIDOPS,
    TEAM_ROCKET_ENERGY,
    WOBBUFFET,
    build_rocket_ledger,
)
from .truth import LegalOption, TruthState


T_PLAY, T_ENERGY, T_ATTACK, T_END = 7, 8, 13, 14
MEWTWO_ERASURE_BALL = 608
SPIDOPS_ROCKET_RUSH = 560
WOBBUFFET_ROCKET_MIRROR = 609


def _active_id(truth: TruthState) -> int:
    return truth.me.active[0].card_id if truth.me.active else -1


class RocketEnergyAttachmentGuard:
    """Team Rocket Energy may only be attached to Team Rocket Pokemon."""

    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ENERGY or option.card_id != TEAM_ROCKET_ENERGY:
            return GuardVote("rocket_energy_attachment")
        if option.target_id < 0:
            return GuardVote(
                "rocket_energy_attachment",
                True,
                reason="Team Rocket Energy target unresolved; fail closed",
            )
        if option.target_id not in ROCKET_POKEMON:
            return GuardVote(
                "rocket_energy_attachment",
                True,
                reason=f"Team Rocket Energy cannot attach to card_id={option.target_id}",
            )
        return GuardVote("rocket_energy_attachment", bonus=70, reason="legal Rocket attachment")


class MewtwoAttackReadinessGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ATTACK or option.attack_id != MEWTWO_ERASURE_BALL:
            return GuardVote("mewtwo_attack_readiness")
        ledger = build_rocket_ledger(truth)
        if _active_id(truth) != MEWTWO_EX:
            return GuardVote("mewtwo_attack_readiness", True, reason="Erasure Ball source is not active Mewtwo")
        if not ledger.four_rocket_online:
            return GuardVote(
                "mewtwo_attack_readiness",
                True,
                reason=f"Power Saver active: rocket_count={ledger.rocket_count}<4",
            )
        if not ledger.active_mewtwo_ready:
            return GuardVote(
                "mewtwo_attack_readiness",
                True,
                reason="Mewtwo lacks 2 Psychic plus 1 additional Energy unit",
            )
        return GuardVote("mewtwo_attack_readiness", bonus=110, reason="Mewtwo attack contract ready")


class ErasureBallSpecialEnergyGuard:
    """Preserve nonrenewable Team Rocket Energy during Erasure Ball payment."""

    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if _active_id(truth) != MEWTWO_EX or truth.max_count > 2:
            return GuardVote("erasure_special_energy")
        energy_options = [
            candidate for candidate in truth.options
            if candidate.card_id in BASIC_ENERGY_IDS or candidate.card_id == TEAM_ROCKET_ENERGY
        ]
        if len(energy_options) != len(truth.options) or not energy_options:
            return GuardVote("erasure_special_energy")
        basics = [candidate for candidate in energy_options if candidate.card_id in BASIC_ENERGY_IDS]
        if option.card_id == TEAM_ROCKET_ENERGY and len(basics) >= truth.min_count:
            return GuardVote(
                "erasure_special_energy",
                True,
                reason="renewable Basic Energy alternatives exist; preserve Team Rocket Energy",
            )
        if option.card_id in BASIC_ENERGY_IDS:
            return GuardVote("erasure_special_energy", bonus=100, reason="Spidops can recycle Basic Energy")
        return GuardVote("erasure_special_energy")


class MewtwoTerminalEndGuard:
    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_END:
            return GuardVote("mewtwo_terminal_end")
        ledger = build_rocket_ledger(truth)
        active = _active_id(truth)
        for candidate in truth.options:
            if candidate.action_type != T_ATTACK:
                continue
            if candidate.attack_id == MEWTWO_ERASURE_BALL and ledger.exact_mewtwo_terminal:
                return GuardVote("mewtwo_terminal_end", True, reason="END misses exact Erasure Ball KO")
            if candidate.attack_id == SPIDOPS_ROCKET_RUSH and active == SPIDOPS:
                if 30 * ledger.rocket_count >= ledger.opponent_active_hp > 0:
                    return GuardVote("mewtwo_terminal_end", True, reason="END misses Rocket Rush KO")
            if candidate.attack_id == WOBBUFFET_ROCKET_MIRROR and active == WOBBUFFET:
                if ledger.damaged_rocket_max >= ledger.opponent_active_hp > 0:
                    return GuardVote("mewtwo_terminal_end", True, reason="END misses Rocket Mirror KO")
        return GuardVote("mewtwo_terminal_end")


class RocketBenchReserveGuard:
    """Do not consume the last Bench slot after the four-body condition is met."""

    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_PLAY or option.card_id not in ROCKET_POKEMON:
            return GuardVote("rocket_bench_reserve")
        ledger = build_rocket_ledger(truth)
        if ledger.four_rocket_online and ledger.bench_slots_left <= 1:
            if option.card_id == MEWTWO_EX and ledger.mewtwo_count == 0:
                return GuardVote("rocket_bench_reserve", bonus=70, reason="reserve slot used for first Mewtwo")
            return GuardVote(
                "rocket_bench_reserve",
                penalty=180,
                reason="preserve final Bench slot for attacker/recovery route",
            )
        return GuardVote("rocket_bench_reserve")


def championship_mewtwo_guards() -> tuple:
    return (
        RocketEnergyAttachmentGuard(),
        MewtwoAttackReadinessGuard(),
        ErasureBallSpecialEnergyGuard(),
        MewtwoTerminalEndGuard(),
        RocketBenchReserveGuard(),
    )

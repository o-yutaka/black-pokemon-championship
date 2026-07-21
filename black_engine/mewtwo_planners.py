from __future__ import annotations

from .planners import PlannerVote
from .rocket_ledger import (
    BASIC_ENERGY_IDS,
    MEWTWO_EX,
    MURKROW,
    ROCKET_POKEMON,
    SPIDOPS,
    TEAM_ROCKET_ENERGY,
    WOBBUFFET,
    build_rocket_ledger,
)
from .truth import LegalOption, TruthState


T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK = 7, 8, 9, 10, 12, 13
MEWTWO_ERASURE_BALL = 608
SPIDOPS_ROCKET_RUSH = 560
WOBBUFFET_ROCKET_MIRROR = 609

BUG_CATCHING_SET = 1094
ENERGY_SEARCH = 1119
ROCKET_TRANSCEIVER = 1134
POKE_PAD = 1152
ARIANA = 1216
GIOVANNI = 1218
PETREL = 1219
PROTON = 1220
LILLIE = 1227
ROCKET_FACTORY = 1257

ROCKET_SUPPORTERS = frozenset({ARIANA, GIOVANNI, PETREL, PROTON})


def _active_id(truth: TruthState) -> int:
    return truth.me.active[0].card_id if truth.me.active else -1


class MewtwoPrizeRoutePlanner:
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        ledger = build_rocket_ledger(truth)
        if option.action_type != T_ATTACK:
            return PlannerVote("mewtwo_prize_route")
        if option.attack_id == MEWTWO_ERASURE_BALL and _active_id(truth) == MEWTWO_EX:
            if ledger.exact_mewtwo_terminal:
                return PlannerVote(
                    "mewtwo_prize_route",
                    bonus=320 - 15 * int(ledger.minimum_discard or 0),
                    reason=f"minimum Erasure Ball tier={ledger.minimum_discard}",
                )
            if ledger.opponent_active_hp > 280:
                return PlannerVote(
                    "mewtwo_prize_route",
                    penalty=80,
                    reason="Erasure Ball cannot one-shot current Active; preserve next route",
                )
        if option.attack_id == SPIDOPS_ROCKET_RUSH and _active_id(truth) == SPIDOPS:
            damage = 30 * ledger.rocket_count
            return PlannerVote(
                "mewtwo_prize_route",
                bonus=250 if damage >= ledger.opponent_active_hp > 0 else 40 + damage / 3,
                reason=f"Rocket Rush damage={damage}",
            )
        if option.attack_id == WOBBUFFET_ROCKET_MIRROR and _active_id(truth) == WOBBUFFET:
            if ledger.damaged_rocket_max >= ledger.opponent_active_hp > 0:
                return PlannerVote("mewtwo_prize_route", bonus=290, reason="one-Prize Rocket Mirror lethal")
            return PlannerVote(
                "mewtwo_prize_route",
                bonus=min(150, ledger.damaged_rocket_max / 2),
                reason=f"convert stored damage={ledger.damaged_rocket_max}",
            )
        return PlannerVote("mewtwo_prize_route")


class RocketSetupSequencePlanner:
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        ledger = build_rocket_ledger(truth)
        if option.action_type == T_EVOLVE and option.card_id == SPIDOPS:
            return PlannerVote("rocket_setup_sequence", bonus=210, reason="activate renewable Basic Energy loop")
        if option.action_type == T_ABILITY and option.card_id == SPIDOPS:
            return PlannerVote(
                "rocket_setup_sequence",
                bonus=190 if ledger.basic_energy_in_discard else 40,
                reason="Charging Up restores Erasure Ball fuel",
            )
        if option.action_type != T_PLAY:
            return PlannerVote("rocket_setup_sequence")
        if option.card_id == PROTON and (truth.turn <= 1 or ledger.rocket_count < 4):
            return PlannerVote("rocket_setup_sequence", bonus=220, reason="opening four-Rocket setup")
        if option.card_id in {POKE_PAD, BUG_CATCHING_SET} and ledger.rocket_count < 4:
            return PlannerVote("rocket_setup_sequence", bonus=175, reason="find missing Rocket body")
        if option.card_id == ROCKET_TRANSCEIVER and not truth.me.supporter_played:
            return PlannerVote("rocket_setup_sequence", bonus=180, reason="choose matchup-correct Rocket Supporter")
        if option.card_id == ROCKET_FACTORY:
            supporter_available = any(card in ROCKET_SUPPORTERS for card in truth.me.hand_ids)
            return PlannerVote(
                "rocket_setup_sequence",
                bonus=185 if supporter_available and not truth.me.supporter_played else 80,
                reason="Factory before Rocket Supporter enables draw-two sequence",
            )
        if option.card_id in ROCKET_SUPPORTERS:
            raw = truth.raw_observation
            current = raw.get("current") if isinstance(raw, dict) and isinstance(raw.get("current"), dict) else {}
            stadium = current.get("stadium") if isinstance(current.get("stadium"), list) else []
            stadium_present = any(isinstance(value, dict) and value.get("id") == ROCKET_FACTORY for value in stadium)
            if not stadium_present and ROCKET_FACTORY in truth.me.hand_ids:
                return PlannerVote(
                    "rocket_setup_sequence",
                    penalty=120,
                    reason="play Factory before Rocket Supporter when both are available",
                )
        if option.card_id in ROCKET_POKEMON and ledger.rocket_count < 4:
            return PlannerVote("rocket_setup_sequence", bonus=160, reason="complete Power Saver condition")
        if option.card_id == MURKROW and not truth.me.supporter_played:
            return PlannerVote("rocket_setup_sequence", bonus=120, reason="Deceit access body")
        if option.card_id == LILLIE and ledger.hand_count <= 4:
            return PlannerVote("rocket_setup_sequence", bonus=105, reason="repair low hand")
        return PlannerVote("rocket_setup_sequence")


class RocketResourcePlanner:
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        ledger = build_rocket_ledger(truth)
        if option.action_type == T_ENERGY:
            if option.target_id == SPIDOPS and option.card_id in BASIC_ENERGY_IDS:
                return PlannerVote(
                    "rocket_resource",
                    bonus=180 if ledger.spidops_energy_cards < 2 else 70,
                    reason="build renewable Erasure Ball reservoir",
                )
            if option.target_id == MEWTWO_EX and option.card_id == TEAM_ROCKET_ENERGY:
                return PlannerVote("rocket_resource", bonus=220, reason="two Psychic units plus colorless progress")
            if option.card_id == TEAM_ROCKET_ENERGY and option.target_id not in ROCKET_POKEMON:
                return PlannerVote("rocket_resource", penalty=1000, reason="illegal/unsafe special Energy target")
        if option.action_type == T_RETREAT:
            if ledger.ready_benched_mewtwo and ledger.four_rocket_online and ledger.active_id != MEWTWO_EX:
                return PlannerVote("rocket_resource", bonus=240, reason="handoff attack to ready Mewtwo")
        if option.action_type == T_PLAY and option.card_id == GIOVANNI:
            if ledger.ready_benched_mewtwo and ledger.four_rocket_online:
                return PlannerVote("rocket_resource", bonus=230, reason="switch-gust into Mewtwo Prize turn")
        if option.action_type == T_ATTACK and option.attack_id == MEWTWO_ERASURE_BALL:
            renewable = ledger.maximum_renewable_discard
            if ledger.minimum_discard is not None and renewable >= ledger.minimum_discard:
                return PlannerVote(
                    "rocket_resource",
                    bonus=120,
                    reason=f"discard tier is renewable next turn={renewable}",
                )
            if ledger.minimum_discard == 2 and ledger.bench_special_energy_cards:
                return PlannerVote(
                    "rocket_resource",
                    penalty=130,
                    reason="two-discard route risks nonrenewable Team Rocket Energy",
                )
        return PlannerVote("rocket_resource")


class RocketInformationPlanner:
    def evaluate(self, truth: TruthState, option: LegalOption) -> PlannerVote:
        if option.action_type != T_PLAY:
            return PlannerVote("rocket_information")
        if option.card_id == ROCKET_TRANSCEIVER:
            return PlannerVote("rocket_information", bonus=110, reason="select Supporter after observing current route")
        if option.card_id in {POKE_PAD, BUG_CATCHING_SET, ENERGY_SEARCH}:
            return PlannerVote("rocket_information", bonus=80, reason="resolve constrained search before hand refresh")
        if option.card_id in {ARIANA, LILLIE}:
            unresolved_search = any(
                candidate.action_type == T_PLAY and candidate.card_id in {POKE_PAD, BUG_CATCHING_SET, ENERGY_SEARCH, ROCKET_TRANSCEIVER}
                for candidate in truth.options
            )
            if unresolved_search:
                return PlannerVote("rocket_information", penalty=65, reason="resolve deterministic search before hand refresh")
        return PlannerVote("rocket_information")


def championship_mewtwo_planners() -> tuple:
    return (
        MewtwoPrizeRoutePlanner(),
        RocketSetupSequencePlanner(),
        RocketResourcePlanner(),
        RocketInformationPlanner(),
    )

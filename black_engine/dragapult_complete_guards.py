from __future__ import annotations

from .guards import GuardVote
from .truth import LegalOption, TruthState

T_ABILITY = 10
DRAKLOAK, DRAGAPULT_EX = 120, 121
DUSCLOPS, DUSKNOIR, AZELF = 132, 133, 217
FIRE_ENERGY, PSYCHIC_ENERGY = 2, 5


class CompleteDuskBlastGuard:
    """Cursed Blast spends one Bench body and gives up one Prize.

    Legality is insufficient. The action is admitted only when its full same-turn
    route is visible in public state: direct Prize, Dragapult active conversion,
    or an already funded Azelf terminal. Everything else is hard-rejected.
    """

    def evaluate(self, truth: TruthState, option: LegalOption) -> GuardVote:
        if option.action_type != T_ABILITY or option.card_id not in {DUSCLOPS, DUSKNOIR}:
            return GuardVote("complete_dusk_blast")
        blast = 50 if option.card_id == DUSCLOPS else 130
        if any(0 < pokemon.remaining_hp <= blast for pokemon in truth.opponent.in_play):
            return GuardVote(
                "complete_dusk_blast",
                bonus=300,
                reason=f"Cursed Blast directly converts a Prize within {blast}",
            )

        ready_dragapult = any(
            pokemon.card_id == DRAGAPULT_EX
            and FIRE_ENERGY in pokemon.energy_ids
            and PSYCHIC_ENERGY in pokemon.energy_ids
            for pokemon in truth.me.in_play
        )
        active_hp = truth.opponent.active[0].remaining_hp if truth.opponent.active else 0
        if ready_dragapult and blast < active_hp <= blast + 200:
            return GuardVote(
                "complete_dusk_blast",
                bonus=240,
                reason="Cursed Blast creates immediate Phantom Dive active KO",
            )

        azelf_ready = any(
            pokemon.card_id == AZELF
            and pokemon.energy_count >= 2
            and PSYCHIC_ENERGY in pokemon.energy_ids
            for pokemon in truth.me.in_play
        )
        total_damage = sum(pokemon.damage for pokemon in truth.opponent.in_play)
        if azelf_ready and active_hp > blast and 10 + total_damage + blast >= active_hp:
            return GuardVote(
                "complete_dusk_blast",
                bonus=220,
                reason="Cursed Blast creates immediate funded Azelf terminal",
            )

        return GuardVote(
            "complete_dusk_blast",
            hard_reject=True,
            reason="self-KO has no immediate positive Prize conversion",
        )


def championship_dragapult_guards() -> tuple[CompleteDuskBlastGuard, ...]:
    return (CompleteDuskBlastGuard(),)

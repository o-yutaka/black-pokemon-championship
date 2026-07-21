from __future__ import annotations

from black_lab import card_id

from .dragapult_complete_policy import DragapultCompletePolicy

T_ABILITY, T_RETREAT, T_ATTACK = 10, 12, 13


class DragapultChampionshipPolicy(DragapultCompletePolicy):
    """Submission-facing final policy with source-Pokémon fallback resolution.

    CABT Ability/Retreat/Attack options identify their source through
    inPlayArea/inPlayIndex and can omit area/index/cardId. The Hybrid Truth layer
    already resolves this shape; the deterministic base fallback must do the
    same so fail-closed runtime cannot regress to treating the source as unknown.
    """

    def _resolved_card(self, option: dict, ctx: dict) -> int:
        resolved = super()._resolved_card(option, ctx)
        if resolved >= 0:
            return resolved
        if option.get("type") in {T_ABILITY, T_RETREAT, T_ATTACK}:
            return card_id(self._resolved_target(option, ctx))
        return -1

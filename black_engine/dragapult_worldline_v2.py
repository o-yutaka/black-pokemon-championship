from __future__ import annotations

from typing import Any

from .dragapult_worldline import DragapultWorldlinePolicy as _BaseDragapultWorldlinePolicy
from .policy import (
    CINDERACE,
    DRAGAPULT_EX,
    SWITCH,
    T_PLAY,
    T_RETREAT,
    _missing_colors,
    _prize_value,
)
from .support import bench, card_id, remaining_hp

TAROUNTULA = 400
SPIDOPS = 401
ARTICUNO = 414
ROCKET_MEWTWO_EX = 431
ROCKET_WOBBUFFET = 432
ROCKET_MURKROW = 463
ROCKET_POKEMON = frozenset(
    {TAROUNTULA, SPIDOPS, ARTICUNO, ROCKET_MEWTWO_EX, ROCKET_WOBBUFFET, ROCKET_MURKROW}
)


class DragapultWorldlinePolicy(_BaseDragapultWorldlinePolicy):
    """Championship correction layer for opponent-aware Dragapult routes."""

    def __init__(self) -> None:
        super().__init__()
        self._latest_context: dict[str, Any] | None = None

    def build_context(self, obs: dict) -> dict:
        ctx = super().build_context(obs)
        opponent_rocket = [value for value in ctx["theirs"] if card_id(value) in ROCKET_POKEMON]
        ready_bench = [
            value
            for value in bench(obs, ctx["me"])
            if card_id(value) == DRAGAPULT_EX and _missing_colors(value) == 0
        ]
        ctx.update(
            {
                "rocket_mewtwo_matchup": bool(opponent_rocket),
                "opponent_rocket_count": len(opponent_rocket),
                "opponent_articuno_online": any(card_id(value) == ARTICUNO for value in opponent_rocket),
                "ready_bench_dragapult_count": len(ready_bench),
            }
        )
        self._latest_context = ctx
        return ctx

    def _immediate_prize_pressure(self, ctx: dict) -> bool:
        hp = int(ctx.get("opp_hp", 0) or 0)
        if 0 < hp <= 200:
            return True
        articuno = bool(ctx.get("opponent_articuno_online"))
        for value in ctx.get("theirs", ()):
            if not isinstance(value, dict):
                continue
            target_hp = remaining_hp(value)
            if not 0 < target_hp <= 60:
                continue
            cid = card_id(value)
            protected_basic = articuno and cid in ROCKET_POKEMON and cid != SPIDOPS
            if not protected_basic:
                return True
        return False

    def _plan_for_option(self, index: int, option: dict, ctx: dict):
        result = super()._plan_for_option(index, option, ctx)
        kind = option.get("type")
        cid = self._resolved_option_card(option, ctx)
        if kind == T_RETREAT or (kind == T_PLAY and cid == SWITCH):
            allowed = (
                ctx["active_id"] == CINDERACE
                and ctx["ready_bench_dragapult_count"] > 0
                and self._immediate_prize_pressure(ctx)
            )
            if not allowed:
                result.plan.plan_id = "NO_MANUAL_SWITCH_WITHOUT_ATTACK"
                result.illegal = True
                result.our_attacks_to_win = 9
                result.opponent_attacks_to_win = 1
                result.hostile_survival = 0.01
                result.irreversible_cost = 1.0
                result.opponent_pain = 0.0
                result.regret = 1800.0
                result.confidence = 0.99
        return result

    @staticmethod
    def _resolved_option_card(option: dict, ctx: dict) -> int:
        from .policy import _resolved_card

        return _resolved_card(option, ctx)

    def _bomb_target(self, pokemon: dict, blast: int, ctx: dict) -> float:
        if not ctx.get("rocket_mewtwo_matchup"):
            return super()._bomb_target(pokemon, blast, ctx)

        hp = remaining_hp(pokemon)
        if hp <= 0:
            return -10000
        cid = card_id(pokemon)
        prize = _prize_value(pokemon)
        immediate_ko = hp <= blast
        active_phantom_follow = ctx["active_id"] == DRAGAPULT_EX and ctx["dragapult_ready"]

        if immediate_ko:
            engine_bonus = 1700 if cid == SPIDOPS else 900 if cid == ROCKET_MEWTWO_EX else 500
            count_break = 1800 if ctx["opponent_rocket_count"] <= 4 else 0
            return 10000 + 1200 * prize + engine_bonus + count_break - max(0, blast - hp)
        if active_phantom_follow and hp <= blast + 200:
            engine_bonus = 1200 if cid == SPIDOPS else 600 if cid == ROCKET_MEWTWO_EX else 0
            return 7000 + 900 * prize + engine_bonus
        return -5000

    def _spread_target(self, pokemon: dict) -> float:
        ctx = self._latest_context or {}
        if not ctx.get("rocket_mewtwo_matchup"):
            return super()._spread_target(pokemon)

        hp = remaining_hp(pokemon)
        if hp <= 0:
            return -10000
        cid = card_id(pokemon)
        if ctx.get("opponent_articuno_online") and cid in ROCKET_POKEMON and cid != SPIDOPS:
            return -10000

        base = super()._spread_target(pokemon)
        if hp <= 10:
            base += 10000 + 1200 * _prize_value(pokemon)
        if cid == SPIDOPS:
            base += 3000
        if cid in ROCKET_POKEMON and ctx.get("opponent_rocket_count", 0) <= 4:
            base += 1800
        return base

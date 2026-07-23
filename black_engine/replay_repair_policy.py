from __future__ import annotations

from .championship_policy import ChampionshipRocketMewtwoPolicy as BaseChampionshipPolicy
from .rocket_mewtwo_worldline import (
    CTX_DISCARD,
    CTX_DISCARD_ENERGY_CARD,
    CTX_SETUP_BENCH,
    MEWTWO_EX,
    SPIDOPS,
    T_ATTACK,
    T_END,
    T_ENERGY,
)


class ChampionshipRocketMewtwoPolicy(BaseChampionshipPolicy):
    """Replay-repair layer promoted above the tested championship policy.

    A normal Energy attachment does not close the turn. When the official legal
    option list contains both a turn-closing Attack/End and an attachment that
    advances the first Mewtwo—or a genuinely required second attacker—choose the
    setup action first. Immediate KOs and game-winning attacks are never delayed.
    """

    def _immediate_ko_attack(self, context: dict) -> int | None:
        truth = context["truth"]
        target = truth.opponent_active
        if target is None:
            return None
        values: list[tuple[int, int]] = []
        for option in truth.options:
            if option.action_type != T_ATTACK:
                continue
            damage = self._attack_option_damage(option, context)
            if damage >= target.current_hp > 0:
                values.append((damage, option.action_index))
        return max(values, default=(0, -1))[1] if values else None

    def _second_mewtwo_needed(self, context: dict) -> bool:
        if not context.get("ready_mewtwo") or context.get("backup_attacker_ready"):
            return False
        active = context.get("active")
        if active is None:
            return False
        if active.card_id == SPIDOPS:
            return True
        observed = int(context.get("observed_opponent_damage", 0) or 0)
        return active.card_id == MEWTWO_EX and observed > 0 and observed >= active.current_hp

    def _mewtwo_setup_before_close(self, context: dict) -> int | None:
        truth = context["truth"]
        if not any(option.action_type in {T_ATTACK, T_END} for option in truth.options):
            return None
        # A real Prize-taking KO is tempo, not a setup error. Terminal wins are
        # handled one level above, but every immediate KO is protected here.
        if self._immediate_ko_attack(context) is not None:
            return None

        has_ready = bool(context.get("ready_mewtwo"))
        allow_second = self._second_mewtwo_needed(context)
        candidates = []
        for option in truth.options:
            if option.action_type != T_ENERGY:
                continue
            result = self._plan_for_option(option.action_index, context)
            if result.illegal:
                continue
            if not has_ready and result.plan.plan_id == "FIRST_MEWTWO_READY":
                candidates.append(result)
            elif allow_second and result.plan.plan_id == "SECOND_MEWTWO_DEVELOPMENT":
                candidates.append(result)
        if not candidates:
            return None
        return self.judge.choose(candidates).plan.root_action_index

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        truth = context["truth"]
        special = truth.context == CTX_SETUP_BENCH or (
            truth.context in {CTX_DISCARD, CTX_DISCARD_ENERGY_CARD}
            and truth.effect_card_id == MEWTWO_EX
        )
        ranked = super().choose_multi(options, context, minimum, maximum)
        if special:
            return ranked
        # Optional generic selections are resource commitments. Choose only the
        # mandatory minimum; card-specific effects above retain exact counts.
        return ranked[:minimum] if minimum > 0 else []

    def agent(self, obs: dict | None, configuration=None):
        if obs is None or not isinstance(obs, dict) or obs.get("select") is None:
            return list(self.deck)
        select = obs.get("select") or {}
        options = select.get("option") if isinstance(select.get("option"), list) else []
        if not options:
            return []
        minimum = max(0, int(select.get("minCount", 1) or 0))
        maximum_raw = select.get("maxCount", minimum)
        maximum = minimum if maximum_raw is None else max(0, int(maximum_raw))
        context = self.build_context(obs)
        raw = (
            self.choose_single(options, context)
            if minimum == maximum == 1
            else self.choose_multi(options, context, minimum, maximum)
        )
        values = list(raw) if isinstance(raw, (list, tuple)) else [raw]
        chosen: list[int] = []
        capacity = min(maximum, len(options))
        for value in values:
            if type(value) is int and 0 <= value < len(options) and value not in chosen:
                chosen.append(value)
                if len(chosen) >= capacity:
                    break
        for index in range(len(options)):
            if len(chosen) >= minimum:
                break
            if index not in chosen and len(chosen) < capacity:
                chosen.append(index)
        return chosen[:capacity]

    def choose_single(self, options: list, context: dict) -> int:
        # Never delay a verified game-winning attack.
        if self._terminal_attack(context) is not None:
            return super().choose_single(options, context)

        immediate_ko = self._immediate_ko_attack(context)
        if immediate_ko is not None:
            self.last_runner_id = "IMMEDIATE_KO_FREEZE"
            return immediate_ko

        setup = self._mewtwo_setup_before_close(context)
        if setup is not None:
            self.last_runner_id = "MEWTWO_SETUP_BEFORE_TURN_CLOSE"
            return setup
        return super().choose_single(options, context)

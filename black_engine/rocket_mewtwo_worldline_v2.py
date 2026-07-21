from __future__ import annotations

from .mewtwo_truth import AREA_BENCH, MewtwoOption, MewtwoTruth, PokemonInstance
from .rocket_mewtwo_worldline import (
    ARTICUNO,
    CTX_DISCARD,
    CTX_DISCARD_ENERGY_CARD,
    CTX_TO_HAND,
    GIOVANNI,
    MEWTWO_ERASURE_BALL,
    MEWTWO_EX,
    NIGHT_STRETCHER,
    POKE_PAD,
    ROCKET_POKEMON,
    SPIDOPS,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
    T_ATTACK,
    T_EVOLVE,
    T_PLAY,
    XEROSIC,
    RocketMewtwoWorldlinePolicy as _BaseRocketMewtwoWorldlinePolicy,
    _prize_value,
    minimum_erasure_discards,
    mewtwo_ready,
)

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})


def erasure_damage(discard_count: int) -> int:
    return 160 + 60 * max(0, min(2, int(discard_count)))


def planned_erasure_discards(remaining_hp: int, available_cards: int) -> int:
    """Choose the first-hit discard count for the complete KO route.

    Targets above 280 HP are not an attack rejection. In particular, 320 HP is
    a zero-discard 160 + 160 route, preserving every renewable Energy card.
    """
    hp = max(0, int(remaining_hp))
    available = max(0, min(2, int(available_cards)))
    exact = minimum_erasure_discards(hp)
    if exact is not None:
        return min(exact, available)
    if hp <= 320:
        return 0
    if hp <= 380:
        return min(1, available)
    if hp <= 440:
        return min(2, available)
    return 0


def erasure_attacks_required(remaining_hp: int, first_discard: int) -> int:
    hp = max(0, int(remaining_hp))
    if hp <= 0:
        return 0
    remainder = max(0, hp - erasure_damage(first_discard))
    return 1 + (remainder + 159) // 160


class RocketMewtwoWorldlinePolicy(_BaseRocketMewtwoWorldlinePolicy):
    """Championship correction layer for complete Rocket Mewtwo worldlines."""

    def __init__(self) -> None:
        super().__init__()
        self.attack_reserved = False
        self.last_turn: int | None = None

    def build_context(self, obs: dict) -> dict:
        ctx = super().build_context(obs)
        truth: MewtwoTruth = ctx["truth"]
        if self.last_turn is None or truth.turn != self.last_turn:
            self.attack_reserved = False
            self.last_turn = truth.turn

        opponent_hp = ctx["opponent_hp"]
        planned = planned_erasure_discards(opponent_hp, ctx["bench_energy_cards"])
        attacks = erasure_attacks_required(opponent_hp, planned) if opponent_hp else 99
        dragapult_seen = any(value.card_id in DRAGAPULT_LINE for value in truth.theirs)
        articuno_online = any(value.card_id == ARTICUNO for value in truth.mine)

        spread_budget = 6
        vulnerable_costs: list[int] = []
        for value in truth.mine:
            if value.area != AREA_BENCH or value.card_id not in ROCKET_POKEMON:
                continue
            protected_basic = articuno_online and value.card_id != SPIDOPS
            if protected_basic:
                continue
            vulnerable_costs.append(max(1, (value.current_hp + 9) // 10))

        phantom_kos = 0
        for cost in sorted(vulnerable_costs):
            if cost > spread_budget:
                break
            spread_budget -= cost
            phantom_kos += 1
        survivors = max(0, ctx["rocket_count"] - phantom_kos)
        spread_resilient = survivors >= 4

        ctx.update(
            {
                "planned_discard": planned,
                "erasure_attacks": attacks,
                "dragapult_seen": dragapult_seen,
                "articuno_online": articuno_online,
                "rocket_count_after_phantom": survivors,
                "four_rocket_spread_resilient": spread_resilient,
                "four_rocket_resilient": spread_resilient if dragapult_seen else ctx["rocket_count"] >= 5,
                "spidops_count": len(ctx["spidops"]),
                "second_mewtwo_in_play": len(ctx["mewtwo"]) >= 2,
                "mewtwo_in_discard": MEWTWO_EX in truth.discard_ids,
            }
        )
        return ctx

    def _can_erasure_attack(self, ctx: dict) -> bool:
        return bool(
            ctx["four_rocket_online"]
            and ctx["active_mewtwo_ready"]
            and ctx["opponent_hp"] > 0
        )

    def _xerosic_value(self, ctx: dict) -> tuple[bool, float, str]:
        truth: MewtwoTruth = ctx["truth"]
        if truth.supporter_played:
            return False, 0.0, "supporter_already_played"
        if truth.opponent_hand_count < 6:
            return False, 0.0, "opponent_hand_below_six"
        if self._best_ready_bench(ctx) is not None and not ctx["active_mewtwo_ready"]:
            return False, 0.0, "giovanni_handoff_required"
        if not ctx["four_rocket_online"]:
            return False, 0.0, "rocket_four_incomplete"

        value = 500.0 + 140.0 * max(0, truth.opponent_hand_count - 3)
        reason = "proactive_choke"
        if self._can_erasure_attack(ctx):
            value += 260.0
            reason = "xerosic_then_erasure"
        if not ctx["four_rocket_resilient"]:
            value -= 180.0
        return True, value, reason

    def _best_opponent_gust_target(self, ctx: dict) -> PokemonInstance | None:
        truth: MewtwoTruth = ctx["truth"]
        candidates = [value for value in truth.theirs if value.area == AREA_BENCH]
        return max(
            candidates,
            key=lambda value: (
                -erasure_attacks_required(
                    value.current_hp,
                    planned_erasure_discards(value.current_hp, ctx["bench_energy_cards"]),
                ),
                _prize_value(value),
                value.damage,
                -value.current_hp,
                -value.serial,
            ),
            default=None,
        )

    def _plan_for_option(self, index: int, ctx: dict):
        result = super()._plan_for_option(index, ctx)
        option: MewtwoOption = self._option(ctx, index)
        truth: MewtwoTruth = ctx["truth"]

        if option.action_type == T_ATTACK and option.attack_id == MEWTWO_ERASURE_BALL:
            legal = self._can_erasure_attack(ctx)
            planned = ctx["planned_discard"]
            attacks = ctx["erasure_attacks"]
            immediate_ko = legal and erasure_damage(planned) >= ctx["opponent_hp"] > 0
            result.plan.plan_id = "ERASURE_EXACT_KO" if immediate_ko else "ERASURE_TWO_HIT_PRESSURE"
            result.illegal = not legal
            result.guaranteed_win = immediate_ko and truth.our_prizes == 1
            result.our_attacks_to_win = 0 if result.guaranteed_win else attacks if legal else 9
            result.opponent_attacks_to_win = 2 if ctx["four_rocket_resilient"] else 1
            result.hostile_survival = 0.97 if immediate_ko else 0.88 if legal else 0.01
            result.opponent_pain = (1300.0 if immediate_ko else 980.0) + 40.0 * (2 - planned)
            result.regret = 0.0 if legal else 1500.0
            result.confidence = 0.99
            result.metadata.update({"planned_discard": planned, "planned_damage": erasure_damage(planned)})

        elif option.action_type == T_EVOLVE and option.card_id == SPIDOPS:
            preserve = (
                ctx["dragapult_seen"]
                and ctx["articuno_online"]
                and ctx["spidops_count"] >= 1
            )
            if preserve:
                result.plan.plan_id = "HOLD_PROTECTED_BASIC"
                result.illegal = True
                result.our_attacks_to_win = 7
                result.opponent_attacks_to_win = 1
                result.hostile_survival = 0.08
                result.opponent_pain = 0.0
                result.regret = 1400.0
                result.confidence = 0.95

        elif option.action_type == T_PLAY and option.card_id == XEROSIC:
            allowed, value, _ = self._xerosic_value(ctx)
            if allowed and self._can_erasure_attack(ctx):
                result.plan.plan_id = "XEROSIC_THEN_ERASURE"
                result.our_attacks_to_win = ctx["erasure_attacks"]
                result.opponent_pain = value

        elif (
            option.action_type == T_PLAY
            and option.card_id == NIGHT_STRETCHER
            and ctx["mewtwo_in_discard"]
            and not ctx["second_mewtwo_in_play"]
        ):
            result.plan.plan_id = "SECOND_MEWTWO_RECOVERY"
            result.our_attacks_to_win = 2
            result.opponent_attacks_to_win = 2
            result.hostile_survival = 0.90
            result.opponent_pain = 920.0
            result.regret = 0.0
            result.confidence = 0.94

        elif truth.context == CTX_TO_HAND and option.card_id == MEWTWO_EX and not ctx["second_mewtwo_in_play"]:
            result.plan.plan_id = "SECOND_MEWTWO_SEARCH"
            result.opponent_pain = max(result.opponent_pain, 1400.0)
            result.hostile_survival = max(result.hostile_survival, 0.90)

        return result

    def choose_single(self, options: list, context: dict) -> int:
        truth: MewtwoTruth = context["truth"]
        if self.attack_reserved:
            reserved = next(
                (
                    option.action_index
                    for option in truth.options
                    if option.action_type == T_ATTACK
                    and option.attack_id == MEWTWO_ERASURE_BALL
                    and self._can_erasure_attack(context)
                ),
                None,
            )
            if reserved is not None:
                self.last_runner_id = "RESERVED_ERASURE_ATTACK"
                self.attack_reserved = False
                return reserved

        selected = super().choose_single(options, context)
        chosen = truth.options[selected]
        if chosen.action_type == T_PLAY and chosen.card_id == XEROSIC and self._can_erasure_attack(context):
            self.attack_reserved = True
        if chosen.action_type == T_ATTACK:
            self.attack_reserved = False
        return selected

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        truth: MewtwoTruth = context["truth"]
        erasure_window = (
            truth.context in {CTX_DISCARD, CTX_DISCARD_ENERGY_CARD}
            and truth.effect_card_id == MEWTWO_EX
        )
        if erasure_window:
            needed = context["planned_discard"]
            if needed == 0:
                self.last_runner_id = "ERASURE_DISCARD_0"
                return [] if minimum == 0 else [row.action_index for row in truth.options[:minimum]]
            count = min(maximum, max(minimum, needed))
            ranked = sorted(truth.options, key=lambda row: self._discard_priority(row, context), reverse=True)
            chosen = [row.action_index for row in ranked[:count]]
            self.last_runner_id = f"ERASURE_DISCARD_{len(chosen)}"
            return chosen
        return super().choose_multi(options, context, minimum, maximum)

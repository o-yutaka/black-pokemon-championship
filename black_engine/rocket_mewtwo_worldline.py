from __future__ import annotations

from collections import Counter
from typing import Any

from .mewtwo_truth import (
    AREA_ACTIVE,
    AREA_BENCH,
    BASIC_ENERGY_IDS,
    PSYCHIC_ENERGY,
    TEAM_ROCKET_ENERGY,
    MewtwoOption,
    MewtwoTruth,
    PokemonInstance,
    build_mewtwo_truth,
)
from .support import ScoredPolicy
from .worldline import CandidatePlan, CausalJudge, WorldlineResult

T_YES, T_NO = 1, 2
T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
CTX_SETUP_ACTIVE, CTX_SETUP_BENCH = 1, 2
CTX_SWITCH, CTX_TO_ACTIVE, CTX_TO_HAND = 3, 4, 7
CTX_DISCARD, CTX_DISCARD_ENERGY_CARD = 8, 26

TAROUNTULA = 400
SPIDOPS = 401
ARTICUNO = 414
MEWTWO_EX = 431
WOBBUFFET = 432
MURKROW = 463
ROCKET_POKEMON = frozenset({TAROUNTULA, SPIDOPS, ARTICUNO, MEWTWO_EX, WOBBUFFET, MURKROW})

GRASS_ENERGY, WATER_ENERGY = 1, 3
BUG_CATCHING_SET = 1094
NIGHT_STRETCHER = 1097
ENERGY_SEARCH = 1119
ROCKET_TRANSCEIVER = 1134
POKE_PAD = 1152
HEROES_CAPE = 1159
XEROSIC = 1197
ARIANA = 1216
ARCHER = 1217
GIOVANNI = 1218
PETREL = 1219
PROTON = 1220
LILLIE = 1227
ROCKET_FACTORY = 1257

SPIDOPS_ROCKET_RUSH = 560
ARTICUNO_DARK_FROST = 583
MEWTWO_ERASURE_BALL = 608
WOBBUFFET_ROCKET_MIRROR = 609
WOBBUFFET_HEADBUTT = 610
MURKROW_DECEIT = 652
MURKROW_TORMENT = 653


def minimum_erasure_discards(remaining_hp: int) -> int | None:
    hp = max(0, int(remaining_hp))
    if hp <= 160:
        return 0
    if hp <= 220:
        return 1
    if hp <= 280:
        return 2
    return None


def mewtwo_ready(pokemon: PokemonInstance | None) -> bool:
    return bool(
        pokemon
        and pokemon.card_id == MEWTWO_EX
        and pokemon.psychic_units >= 2
        and pokemon.total_energy_units >= 3
    )


def readiness_gap(pokemon: PokemonInstance) -> tuple[int, int]:
    return (
        max(0, 2 - pokemon.psychic_units),
        max(0, 3 - pokemon.total_energy_units),
    )


def _prize_value(pokemon: PokemonInstance) -> int:
    return 2 if pokemon.max_hp >= 210 else 1


class RocketMewtwoWorldlinePolicy(ScoredPolicy):
    """Plan-first Rocket Mewtwo policy with serial-safe targeting."""

    def __init__(self) -> None:
        super().__init__()
        self.judge = CausalJudge()
        self.last_runner_id = "BOOT"
        self.desired_active_serial: int | None = None
        self.desired_opponent_serial: int | None = None

    def build_context(self, obs: dict) -> dict:
        truth = build_mewtwo_truth(obs)
        rocket_count = sum(value.card_id in ROCKET_POKEMON for value in truth.mine)
        mewtwo = tuple(value for value in truth.mine if value.card_id == MEWTWO_EX)
        ready = tuple(value for value in mewtwo if mewtwo_ready(value))
        ready_bench = tuple(value for value in ready if value.area == AREA_BENCH)
        spidops = tuple(value for value in truth.mine if value.card_id == SPIDOPS)
        bench_energy_cards = sum(len(value.energy_card_ids) for value in truth.mine if value.area == AREA_BENCH)
        bench_basic_energy_cards = sum(
            card in BASIC_ENERGY_IDS
            for value in truth.mine
            if value.area == AREA_BENCH
            for card in value.energy_card_ids
        )
        basic_discard = sum(card in BASIC_ENERGY_IDS for card in truth.discard_ids)
        active = truth.active
        opponent_active = truth.opponent_active
        opponent_hp = opponent_active.current_hp if opponent_active is not None else 0
        minimum_discard = minimum_erasure_discards(opponent_hp) if opponent_hp else None
        return {
            "truth": truth,
            "rocket_count": rocket_count,
            "four_rocket_online": rocket_count >= 4,
            "four_rocket_resilient": rocket_count >= 5,
            "mewtwo": mewtwo,
            "ready_mewtwo": ready,
            "ready_bench_mewtwo": ready_bench,
            "spidops": spidops,
            "active": active,
            "active_mewtwo_ready": mewtwo_ready(active),
            "bench_energy_cards": bench_energy_cards,
            "bench_basic_energy_cards": bench_basic_energy_cards,
            "basic_energy_in_discard": basic_discard,
            "minimum_discard": minimum_discard,
            "opponent_hp": opponent_hp,
            "hand_count": len(truth.hand_ids),
            "hand_counts": Counter(truth.hand_ids),
        }

    @staticmethod
    def _option(ctx: dict, index: int) -> MewtwoOption:
        truth: MewtwoTruth = ctx["truth"]
        return truth.options[index]

    @staticmethod
    def _instance(ctx: dict, serial: int | None, *, opponent: bool = False) -> PokemonInstance | None:
        truth: MewtwoTruth = ctx["truth"]
        player_index = truth.opponent if opponent else truth.actor
        return truth.by_serial(player_index, serial)

    def _target_for_energy(self, option: MewtwoOption, ctx: dict) -> PokemonInstance | None:
        return self._instance(ctx, option.target_serial)

    def _best_ready_bench(self, ctx: dict) -> PokemonInstance | None:
        values: tuple[PokemonInstance, ...] = ctx["ready_bench_mewtwo"]
        return min(values, key=lambda value: (len(value.energy_card_ids), value.serial), default=None)

    def _best_opponent_gust_target(self, ctx: dict) -> PokemonInstance | None:
        truth: MewtwoTruth = ctx["truth"]
        needed = ctx["minimum_discard"]
        candidates = [value for value in truth.theirs if value.area == AREA_BENCH]
        return max(
            candidates,
            key=lambda value: (
                needed is not None and value.current_hp <= 160 + 60 * min(2, ctx["bench_energy_cards"]),
                _prize_value(value),
                value.damage,
                -value.current_hp,
                -value.serial,
            ),
            default=None,
        )

    def _can_erasure_attack(self, ctx: dict) -> bool:
        return bool(
            ctx["four_rocket_online"]
            and ctx["active_mewtwo_ready"]
            and ctx["minimum_discard"] is not None
            and ctx["bench_energy_cards"] >= ctx["minimum_discard"]
        )

    def _xerosic_value(self, ctx: dict) -> tuple[bool, float, str]:
        truth: MewtwoTruth = ctx["truth"]
        if truth.supporter_played:
            return False, 0.0, "supporter_already_played"
        if truth.opponent_hand_count < 6:
            return False, 0.0, "opponent_hand_below_six"
        if self._can_erasure_attack(ctx):
            return False, 0.0, "immediate_attack_or_ko_available"
        if self._best_ready_bench(ctx) is not None and not ctx["active_mewtwo_ready"]:
            return False, 0.0, "giovanni_handoff_required"
        if not ctx["four_rocket_online"]:
            return False, 0.0, "rocket_four_incomplete"
        value = 500.0 + 140.0 * max(0, truth.opponent_hand_count - 3)
        if not ctx["four_rocket_resilient"]:
            value -= 180.0
        return True, value, "proactive_choke"

    def _energy_plan(self, option: MewtwoOption, ctx: dict) -> tuple[str, float, float, int, int]:
        target = self._target_for_energy(option, ctx)
        energy = option.card_id
        if target is None:
            return "UNRESOLVED_ENERGY_TARGET", 0.0, 2000.0, 6, 0
        if energy == TEAM_ROCKET_ENERGY and target.card_id not in ROCKET_POKEMON:
            return "ILLEGAL_ROCKET_ENERGY_TARGET", 0.0, 5000.0, 9, 0

        if target.card_id == MEWTWO_EX:
            psychic_gap, total_gap = readiness_gap(target)
            if mewtwo_ready(target):
                return "READY_MEWTWO_OVERATTACH", 0.0, 1600.0, 6, 1
            ready_exists = bool(ctx["ready_mewtwo"])
            if energy == TEAM_ROCKET_ENERGY:
                gain = 2 * int(psychic_gap > 0) + 2 * int(total_gap > 0)
                return (
                    "SECOND_MEWTWO_DEVELOPMENT" if ready_exists else "FIRST_MEWTWO_READY",
                    900.0 + 180.0 * gain,
                    0.15,
                    1,
                    2,
                )
            if energy == PSYCHIC_ENERGY:
                gain = int(psychic_gap > 0) + int(total_gap > 0)
                return (
                    "SECOND_MEWTWO_DEVELOPMENT" if ready_exists else "FIRST_MEWTWO_READY",
                    700.0 + 150.0 * gain,
                    0.10,
                    1,
                    2,
                )
            gain = int(total_gap > 0)
            return (
                "SECOND_MEWTWO_DEVELOPMENT" if ready_exists else "FIRST_MEWTWO_READY",
                480.0 + 120.0 * gain,
                0.10,
                2,
                2,
            )

        if target.card_id == SPIDOPS:
            if not ctx["ready_mewtwo"]:
                return "BATTERY_BEFORE_ATTACKER", 120.0, 500.0, 4, 1
            if energy == TEAM_ROCKET_ENERGY:
                return "PROTECT_TEAM_ROCKET_ENERGY", 0.0, 1200.0, 5, 1
            if energy in BASIC_ENERGY_IDS:
                return "SPIDOPS_BATTERY", 640.0, 0.10, 2, 2

        if target.card_id == ARTICUNO:
            if energy == WATER_ENERGY and WATER_ENERGY not in target.energy_card_ids:
                return "ARTICUNO_BACKUP", 400.0, 0.15, 3, 2
            if energy == TEAM_ROCKET_ENERGY and WATER_ENERGY in target.energy_card_ids:
                return "ARTICUNO_BACKUP", 360.0, 0.30, 3, 2

        return "LOW_VALUE_ATTACHMENT", 80.0, 300.0, 5, 1

    def _plan_for_option(self, index: int, ctx: dict) -> WorldlineResult:
        option = self._option(ctx, index)
        truth: MewtwoTruth = ctx["truth"]
        cid = option.card_id
        kind = option.action_type
        plan_id = "SAFE_LEGAL"
        illegal = False
        immediate_loss = False
        guaranteed_win = False
        prevents_forced_loss = False
        our_attacks = 4
        opponent_attacks = 1
        hostile_survival = 0.30
        irreversible_cost = 0.0
        pain = 20.0
        regret = 400.0
        confidence = 0.55

        if truth.context == CTX_SETUP_ACTIVE:
            plan_id = "ROCKET_SETUP_ACTIVE"
            order = {MURKROW: 5, ARTICUNO: 4, TAROUNTULA: 3, WOBBUFFET: 2, MEWTWO_EX: 1}
            pain = 100.0 * order.get(cid, 0)
            our_attacks = 2
            opponent_attacks = 2
            hostile_survival = 0.72
            regret = 0.0
            confidence = 0.85
        elif truth.context == CTX_SETUP_BENCH:
            plan_id = "ROCKET_ASSEMBLY"
            order = {MEWTWO_EX: 6, TAROUNTULA: 5, MURKROW: 4, ARTICUNO: 3, WOBBUFFET: 2}
            pain = 120.0 * order.get(cid, 0)
            our_attacks = 2
            opponent_attacks = 2 if ctx["rocket_count"] + 1 >= 5 else 1
            hostile_survival = 0.86 if ctx["rocket_count"] + 1 >= 5 else 0.68
            regret = 0.0
            confidence = 0.90
        elif kind == T_ENERGY:
            plan_id, pain, irreversible_cost, our_attacks, opponent_attacks = self._energy_plan(option, ctx)
            hostile_survival = 0.90 if plan_id in {"FIRST_MEWTWO_READY", "SECOND_MEWTWO_DEVELOPMENT"} else 0.60
            regret = 0.0 if pain >= 500 else 700.0
            confidence = 0.95 if option.target_serial is not None else 0.20
            illegal = plan_id in {"UNRESOLVED_ENERGY_TARGET", "ILLEGAL_ROCKET_ENERGY_TARGET"}
        elif kind == T_ATTACK:
            active = ctx["active"]
            active_id = active.card_id if active else -1
            if active_id == MEWTWO_EX and option.attack_id == MEWTWO_ERASURE_BALL:
                plan_id = "ERASURE_MINIMUM_DISCARD"
                legal_attack = self._can_erasure_attack(ctx)
                illegal = not legal_attack
                guaranteed_win = legal_attack and truth.our_prizes == 1
                our_attacks = 0 if guaranteed_win else 1 if legal_attack else 9
                opponent_attacks = 2 if ctx["four_rocket_resilient"] else 1
                hostile_survival = 0.97 if legal_attack else 0.01
                pain = 1300.0 if legal_attack else 0.0
                regret = 0.0 if legal_attack else 1500.0
                confidence = 0.99
            elif active_id == SPIDOPS and option.attack_id == SPIDOPS_ROCKET_RUSH:
                damage = 30 * ctx["rocket_count"]
                plan_id = "SPIDOPS_SINGLE_PRIZE"
                guaranteed_win = damage >= ctx["opponent_hp"] > 0 and truth.our_prizes == 1
                our_attacks = 0 if guaranteed_win else 1 if damage >= ctx["opponent_hp"] > 0 else 3
                opponent_attacks = 2
                hostile_survival = 0.82
                pain = 600.0 + damage
                regret = 0.0
                confidence = 0.95
            elif active_id == WOBBUFFET and option.attack_id == WOBBUFFET_ROCKET_MIRROR:
                plan_id = "WOBBUFFET_TRANSFER"
                max_damage = max((value.damage for value in truth.mine if value.area == AREA_BENCH), default=0)
                our_attacks = 1 if max_damage >= ctx["opponent_hp"] > 0 else 3
                opponent_attacks = 2
                hostile_survival = 0.74
                pain = 420.0 + max_damage
                regret = 0.0
                confidence = 0.90
            elif active_id == ARTICUNO and option.attack_id == ARTICUNO_DARK_FROST:
                plan_id = "ARTICUNO_BACKUP"
                damage = 120 if TEAM_ROCKET_ENERGY in active.energy_card_ids else 60
                our_attacks = 1 if damage >= ctx["opponent_hp"] > 0 else 3
                opponent_attacks = 2
                hostile_survival = 0.72
                pain = 350.0 + damage
                regret = 0.0
                confidence = 0.92
            elif active_id == MURKROW and option.attack_id == MURKROW_DECEIT:
                plan_id = "MURKROW_SUPPORTER_SEARCH"
                our_attacks = 3
                opponent_attacks = 2
                hostile_survival = 0.70
                pain = 450.0 if not truth.supporter_played else 120.0
                regret = 0.0
                confidence = 0.90
            elif active_id == MURKROW and option.attack_id == MURKROW_TORMENT:
                plan_id = "MURKROW_TORMENT"
                our_attacks = 3
                opponent_attacks = 3
                hostile_survival = 0.76
                pain = 500.0
                regret = 0.0
                confidence = 0.75
        elif kind == T_ABILITY and cid == SPIDOPS:
            plan_id = "SPIDOPS_BATTERY"
            available = ctx["basic_energy_in_discard"] > 0
            illegal = not available
            our_attacks = 2 if available else 5
            opponent_attacks = 2
            hostile_survival = 0.82 if available else 0.20
            pain = 620.0 if available else 0.0
            regret = 0.0 if available else 800.0
            confidence = 0.95
        elif kind == T_EVOLVE and cid == SPIDOPS:
            plan_id = "SPIDOPS_ENGINE_EVOLVE"
            our_attacks = 2
            opponent_attacks = 2
            hostile_survival = 0.84
            pain = 580.0
            regret = 0.0
            confidence = 0.95
        elif kind == T_PLAY:
            if cid == XEROSIC:
                allowed, value, reason = self._xerosic_value(ctx)
                plan_id = "XEROSIC_PROACTIVE_CHOKE"
                illegal = not allowed
                our_attacks = 2 if allowed else 7
                opponent_attacks = 3 if allowed else 1
                hostile_survival = 0.86 if allowed else 0.05
                irreversible_cost = 0.80
                pain = value
                regret = 0.0 if allowed else 1300.0
                confidence = 0.82
            elif cid == GIOVANNI:
                ready = self._best_ready_bench(ctx)
                target = self._best_opponent_gust_target(ctx)
                allowed = ready is not None and ctx["four_rocket_online"]
                plan_id = "GIOVANNI_DOUBLE_CONTROL"
                illegal = not allowed
                our_attacks = 1 if allowed else 7
                opponent_attacks = 2 if allowed else 1
                hostile_survival = 0.92 if allowed else 0.08
                irreversible_cost = 0.70
                pain = 1000.0 if allowed and target is not None else 720.0 if allowed else 0.0
                regret = 0.0 if allowed else 1200.0
                confidence = 0.95
            elif cid == PROTON:
                plan_id = "ROCKET_ASSEMBLY"
                need = ctx["rocket_count"] < 4 or truth.turn <= 1
                our_attacks = 2 if need else 4
                opponent_attacks = 2 if ctx["rocket_count"] + 3 >= 5 else 1
                hostile_survival = 0.92 if need else 0.42
                pain = 850.0 if need else 120.0
                regret = 0.0 if need else 500.0
                confidence = 0.96
            elif cid == ARCHER:
                plan_id = "ARCHER_REACTIVE_LOCK"
                allowed = not truth.supporter_played
                our_attacks = 2 if allowed else 7
                opponent_attacks = 3 if allowed else 1
                hostile_survival = 0.84 if allowed else 0.05
                pain = 780.0 if allowed else 0.0
                regret = 0.0 if allowed else 900.0
                confidence = 0.70
            elif cid == ARIANA:
                plan_id = "ARIANA_FACTORY_RECOVERY"
                value = ctx["hand_count"] <= 4
                our_attacks = 2 if value else 4
                opponent_attacks = 2
                hostile_survival = 0.82 if value else 0.50
                pain = 650.0 if value else 180.0
                regret = 0.0 if value else 400.0
                confidence = 0.90
            elif cid == ROCKET_FACTORY:
                plan_id = "FACTORY_DRAW_ENGINE"
                our_attacks = 3
                opponent_attacks = 2
                hostile_survival = 0.68
                pain = 380.0
                regret = 0.0
                confidence = 0.85
            elif cid == ROCKET_TRANSCEIVER:
                plan_id = "ROCKET_SUPPORTER_ROUTE"
                our_attacks = 2
                opponent_attacks = 2
                hostile_survival = 0.78
                pain = 520.0
                regret = 0.0
                confidence = 0.90
            elif cid == POKE_PAD:
                plan_id = "ROCKET_ASSEMBLY"
                need = ctx["rocket_count"] < 5
                our_attacks = 2 if need else 4
                opponent_attacks = 2 if need else 1
                hostile_survival = 0.74 if need else 0.40
                pain = 480.0 if need else 100.0
                regret = 0.0 if need else 350.0
                confidence = 0.88
            elif cid in {BUG_CATCHING_SET, ENERGY_SEARCH, NIGHT_STRETCHER, LILLIE, HEROES_CAPE, PETREL}:
                plan_id = "RESOURCE_RECOVERY"
                our_attacks = 3
                opponent_attacks = 2
                hostile_survival = 0.62
                pain = 280.0
                regret = 0.0
                confidence = 0.78
        elif kind == T_RETREAT:
            ready = self._best_ready_bench(ctx)
            allowed = ready is not None and ctx["four_rocket_online"] and not ctx["active_mewtwo_ready"]
            plan_id = "ACTIVE_HANDOFF"
            illegal = not allowed
            our_attacks = 1 if allowed else 7
            opponent_attacks = 2 if allowed else 1
            hostile_survival = 0.88 if allowed else 0.04
            irreversible_cost = 0.50
            pain = 700.0 if allowed else 0.0
            regret = 0.0 if allowed else 1100.0
            confidence = 0.95
        elif kind == T_END:
            plan_id = "END_ONLY_WHEN_NO_ROUTE"
            our_attacks = 9
            opponent_attacks = 1
            hostile_survival = 0.01
            pain = 0.0
            regret = 1700.0
            confidence = 0.99
        elif truth.context == CTX_TO_HAND:
            plan_id = "SEARCH_ROUTE_CARD"
            route_value = {
                MEWTWO_EX: 900,
                SPIDOPS: 850,
                TAROUNTULA: 800,
                PROTON: 780,
                GIOVANNI: 760,
                XEROSIC: 560 if truth.opponent_hand_count >= 6 else 80,
                ARIANA: 500,
                TEAM_ROCKET_ENERGY: 740,
                PSYCHIC_ENERGY: 600,
                GRASS_ENERGY: 520,
            }.get(cid, 180)
            our_attacks = 2
            opponent_attacks = 2
            hostile_survival = 0.70
            pain = float(route_value)
            regret = 0.0
            confidence = 0.85

        return WorldlineResult(
            plan=CandidatePlan(
                plan_id=plan_id,
                goal="force the opponent's worst prize and reconstruction route",
                root_action_index=index,
                reserved_serials=tuple(
                    serial
                    for serial in (option.source_serial, option.target_serial)
                    if serial is not None
                ),
                abort_conditions=("serial_mismatch", "rocket_four_broken", "illegal_transition"),
                evidence=(f"card={cid}", f"context={truth.context}"),
            ),
            illegal=illegal,
            immediate_loss=immediate_loss,
            guaranteed_win=guaranteed_win,
            prevents_forced_loss=prevents_forced_loss,
            our_attacks_to_win=our_attacks,
            opponent_attacks_to_win=opponent_attacks,
            hostile_survival=hostile_survival,
            irreversible_cost=irreversible_cost,
            opponent_pain=pain,
            regret=regret,
            confidence=confidence,
            metadata={
                "card_id": cid,
                "option_type": kind,
                "source_serial": option.source_serial,
                "target_serial": option.target_serial,
            },
        )

    def score_option(self, option: dict, context: dict) -> float:
        truth: MewtwoTruth = context["truth"]
        index = next((row.action_index for row in truth.options if row.raw is option), None)
        if index is None:
            return -10000.0
        result = self._plan_for_option(index, context)
        key = self.judge.key(result)
        return float(sum((position + 1) * (1 if bool(value) else 0) for position, value in enumerate(key[:4]))) + result.opponent_pain - result.regret

    def _choose_bound_serial(self, ctx: dict, desired: int, *, opponent: bool) -> int | None:
        truth: MewtwoTruth = ctx["truth"]
        expected_player = truth.opponent if opponent else truth.actor
        for option in truth.options:
            raw_player = option.raw.get("playerIndex", expected_player)
            if type(raw_player) is int and raw_player != expected_player:
                continue
            if option.target_serial == desired or option.source_serial == desired:
                return option.action_index
        return None

    def choose_single(self, options: list, context: dict) -> int:
        truth: MewtwoTruth = context["truth"]
        if truth.context in {CTX_SWITCH, CTX_TO_ACTIVE}:
            if self.desired_active_serial is not None:
                exact = self._choose_bound_serial(context, self.desired_active_serial, opponent=False)
                if exact is not None:
                    self.last_runner_id = "GIOVANNI_SELF_HANDOFF"
                    self.desired_active_serial = None
                    return exact
            if self.desired_opponent_serial is not None:
                exact = self._choose_bound_serial(context, self.desired_opponent_serial, opponent=True)
                if exact is not None:
                    self.last_runner_id = "GIOVANNI_OPPONENT_GUST"
                    self.desired_opponent_serial = None
                    return exact

        results = [self._plan_for_option(index, context) for index in range(len(truth.options))]
        chosen = self.judge.choose(results)
        self.last_runner_id = chosen.plan.plan_id
        chosen_option = truth.options[chosen.plan.root_action_index]
        if chosen_option.action_type == T_PLAY and chosen_option.card_id == GIOVANNI:
            ready = self._best_ready_bench(context)
            target = self._best_opponent_gust_target(context)
            self.desired_active_serial = ready.serial if ready is not None else None
            self.desired_opponent_serial = target.serial if target is not None else None
        return chosen.plan.root_action_index

    def _discard_priority(self, option: MewtwoOption, ctx: dict) -> tuple:
        source = self._instance(ctx, option.energy_source_serial)
        energy = option.energy_card_id if option.energy_card_id is not None else option.card_id
        unresolved = source is None or energy is None
        from_mewtwo = bool(source and source.card_id == MEWTWO_EX)
        from_spidops = bool(source and source.card_id == SPIDOPS)
        basic = energy in BASIC_ENERGY_IDS if energy is not None else False
        rocket = energy == TEAM_ROCKET_ENERGY
        return (
            not unresolved,
            basic and from_spidops,
            basic and not from_mewtwo,
            not rocket,
            not from_mewtwo,
            -(source.serial if source else 10**9),
            -option.action_index,
        )

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        truth: MewtwoTruth = context["truth"]
        erasure_window = truth.context in {CTX_DISCARD, CTX_DISCARD_ENERGY_CARD} and truth.effect_card_id == MEWTWO_EX
        if erasure_window:
            needed = context["minimum_discard"]
            if needed is None or needed == 0:
                return [] if minimum == 0 else [row.action_index for row in truth.options[:minimum]]
            count = min(maximum, max(minimum, needed))
            ranked = sorted(truth.options, key=lambda row: self._discard_priority(row, context), reverse=True)
            chosen = [row.action_index for row in ranked[:count]]
            self.last_runner_id = f"ERASURE_DISCARD_{len(chosen)}"
            return chosen

        if truth.context == CTX_SETUP_BENCH:
            target = min(maximum, max(minimum, max(0, 5 - context["rocket_count"])))
            results = [self._plan_for_option(index, context) for index in range(len(truth.options))]
            ranked = sorted(results, key=self.judge.key, reverse=True)
            return [row.plan.root_action_index for row in ranked[:target]]

        results = [self._plan_for_option(index, context) for index in range(len(truth.options))]
        ranked = sorted(results, key=self.judge.key, reverse=True)
        positive = [row for row in ranked if not row.illegal]
        count = min(maximum, max(minimum, len(positive)))
        return [row.plan.root_action_index for row in (positive or ranked)[:count]]

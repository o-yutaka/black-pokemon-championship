from __future__ import annotations

from .mewtwo_truth import AREA_BENCH, MewtwoOption, MewtwoTruth, PokemonInstance
from .prize_truth import prize_value
from .rocket_mewtwo_worldline import (
    ARTICUNO,
    CTX_SWITCH,
    CTX_TO_ACTIVE,
    MEWTWO_ERASURE_BALL,
    MEWTWO_EX,
    MURKROW,
    SPIDOPS,
    SPIDOPS_ROCKET_RUSH,
    TEAM_ROCKET_ENERGY,
    T_ATTACK,
    T_END,
    T_PLAY,
    WOBBUFFET,
    mewtwo_ready,
)
from .rocket_mewtwo_worldline_v2 import (
    RocketMewtwoWorldlinePolicy,
    erasure_damage,
)

LONG_HORIZON_RESOURCE_CARDS = frozenset(
    {
        1094,
        1097,
        1119,
        1134,
        1152,
        1216,
        1217,
        1219,
        1220,
        1227,
        1257,
    }
)


class ChampionshipRocketMewtwoPolicy(RocketMewtwoWorldlinePolicy):
    """Official-observation championship layer for Rocket Mewtwo."""

    def __init__(self) -> None:
        super().__init__()
        self.observed_damage_by_attacker: dict[int, int] = {}
        self.nonpersistent_attack_pairs: set[tuple[int, int, int]] = set()
        self._pending_attack: tuple[int, int, int, int, int, int] | None = None
        self._previous_mine_hp: dict[int, int] = {}
        self._previous_opponent_active_id: int | None = None

    def reset_episode(self) -> None:
        """Clear all evidence that is valid only inside one battle."""
        self.observed_damage_by_attacker.clear()
        self.nonpersistent_attack_pairs.clear()
        self._pending_attack = None
        self._previous_mine_hp.clear()
        self._previous_opponent_active_id = None
        self.desired_active_serial = None
        self.desired_opponent_serial = None
        self.last_runner_id = "BOOT"
        if hasattr(self, "pending"):
            self.pending.clear()
        if hasattr(self, "last_turn"):
            self.last_turn = None

    @staticmethod
    def _player(raw: dict, index: int) -> dict:
        current = raw.get("current") if isinstance(raw.get("current"), dict) else {}
        players = current.get("players") if isinstance(current.get("players"), list) else []
        if 0 <= index < len(players) and isinstance(players[index], dict):
            return players[index]
        return {}

    @staticmethod
    def _deck_count(raw: dict, actor: int) -> int:
        player = ChampionshipRocketMewtwoPolicy._player(raw, actor)
        value = player.get("deckCount")
        if type(value) is int:
            return max(0, value)
        deck = player.get("deck")
        return len(deck) if isinstance(deck, list) else 0

    @staticmethod
    def _energy_units(value: PokemonInstance) -> int:
        return value.total_energy_units

    def _pokemon_attack_ready(self, value: PokemonInstance, ctx: dict) -> bool:
        if value.card_id == MEWTWO_EX:
            return bool(ctx["four_rocket_online"] and mewtwo_ready(value))
        if value.card_id == SPIDOPS:
            return value.total_energy_units >= 1
        if value.card_id == ARTICUNO:
            return value.total_energy_units >= 2
        if value.card_id in {MURKROW, WOBBUFFET}:
            return value.total_energy_units >= 1
        return False

    def _pokemon_damage(self, value: PokemonInstance, ctx: dict) -> int:
        if not self._pokemon_attack_ready(value, ctx):
            return 0
        if value.card_id == MEWTWO_EX:
            return erasure_damage(ctx["planned_discard"])
        if value.card_id == SPIDOPS:
            return 30 * ctx["rocket_count"]
        if value.card_id == ARTICUNO:
            return 120 if TEAM_ROCKET_ENERGY in value.energy_card_ids else 60
        return 0

    def _attack_option_damage(self, option: MewtwoOption, ctx: dict) -> int:
        active: PokemonInstance | None = ctx["active"]
        if active is None or option.action_type != T_ATTACK:
            return 0
        if active.card_id == MEWTWO_EX and option.attack_id == MEWTWO_ERASURE_BALL:
            return erasure_damage(ctx["planned_discard"])
        if active.card_id == SPIDOPS and option.attack_id == SPIDOPS_ROCKET_RUSH:
            return 30 * ctx["rocket_count"]
        return self._pokemon_damage(active, ctx)

    def _pair_key(self, option: MewtwoOption, ctx: dict) -> tuple[int, int, int] | None:
        active: PokemonInstance | None = ctx["active"]
        target: PokemonInstance | None = ctx["truth"].opponent_active
        if active is None or target is None or option.action_type != T_ATTACK:
            return None
        return (active.card_id, option.attack_id, target.card_id)

    def _observe_previous_attack(self, truth: MewtwoTruth) -> None:
        pending = self._pending_attack
        if pending is None:
            return
        attacker_id, attack_id, target_serial, target_card_id, hp_before, attack_turn = pending
        target = truth.by_serial(truth.opponent, target_serial)
        key = (attacker_id, attack_id, target_card_id)
        if target is not None and target.current_hp < hp_before:
            self.nonpersistent_attack_pairs.discard(key)
            self._pending_attack = None
            return
        if target is None:
            self._pending_attack = None
            return
        if truth.turn == attack_turn:
            return
        self.nonpersistent_attack_pairs.add(key)
        self._pending_attack = None

    def _observe_incoming_damage(self, truth: MewtwoTruth) -> None:
        if self._previous_mine_hp and self._previous_opponent_active_id is not None:
            current = {value.serial: value.current_hp for value in truth.mine}
            observed = 0
            for serial, old_hp in self._previous_mine_hp.items():
                new_hp = current.get(serial, 0)
                observed = max(observed, max(0, old_hp - new_hp))
            if observed > 0:
                attacker = self._previous_opponent_active_id
                self.observed_damage_by_attacker[attacker] = max(
                    observed,
                    self.observed_damage_by_attacker.get(attacker, 0),
                )
        self._previous_mine_hp = {value.serial: value.current_hp for value in truth.mine}
        opponent_active = truth.opponent_active
        self._previous_opponent_active_id = opponent_active.card_id if opponent_active else None

    def build_context(self, obs: dict) -> dict:
        ctx = super().build_context(obs)
        truth: MewtwoTruth = ctx["truth"]
        self._observe_previous_attack(truth)
        self._observe_incoming_damage(truth)
        opponent_active = truth.opponent_active
        opponent_prize_value = prize_value(opponent_active.card_id) if opponent_active else 0
        observed_damage = self.observed_damage_by_attacker.get(opponent_active.card_id, 0) if opponent_active else 0
        ready_bench = tuple(
            value for value in truth.mine
            if value.area == AREA_BENCH and self._pokemon_attack_ready(value, ctx)
        )
        deck_count = self._deck_count(obs, truth.actor)
        estimated_turns_to_win = max(1, truth.our_prizes)
        safe_draw_budget = deck_count - estimated_turns_to_win - 2
        ctx.update(
            {
                "opponent_active_prize_value": opponent_prize_value,
                "game_winning_target": bool(opponent_active and opponent_prize_value >= truth.our_prizes > 0),
                "observed_opponent_damage": observed_damage,
                "ready_bench_attackers": ready_bench,
                "backup_attacker_ready": bool(ready_bench),
                "deck_count": deck_count,
                "estimated_turns_to_win": estimated_turns_to_win,
                "safe_draw_budget": safe_draw_budget,
                "deck_clock_critical": safe_draw_budget <= 0,
            }
        )
        return ctx

    def _terminal_attack(self, ctx: dict) -> int | None:
        truth: MewtwoTruth = ctx["truth"]
        target = truth.opponent_active
        if target is None or not ctx["game_winning_target"]:
            return None
        lethal: list[tuple[int, int]] = []
        for option in truth.options:
            damage = self._attack_option_damage(option, ctx)
            if option.action_type == T_ATTACK and damage >= target.current_hp > 0:
                lethal.append((damage, option.action_index))
        return max(lethal, default=(0, -1))[1] if lethal else None

    def _promotion_candidate(self, option: MewtwoOption, ctx: dict) -> PokemonInstance | None:
        truth: MewtwoTruth = ctx["truth"]
        serial = option.target_serial if option.target_serial is not None else option.source_serial
        return truth.by_serial(truth.actor, serial)

    def _promotion_choice(self, ctx: dict) -> int | None:
        truth: MewtwoTruth = ctx["truth"]
        if truth.context not in {CTX_SWITCH, CTX_TO_ACTIVE}:
            return None
        candidates: list[tuple[MewtwoOption, PokemonInstance]] = []
        for option in truth.options:
            value = self._promotion_candidate(option, ctx)
            if value is not None:
                candidates.append((option, value))
        if not candidates:
            return None
        target = truth.opponent_active
        if target is not None and ctx["game_winning_target"]:
            winning = [
                (self._pokemon_damage(value, ctx), option.action_index)
                for option, value in candidates
                if self._pokemon_damage(value, ctx) >= target.current_hp > 0
            ]
            if winning:
                self.last_runner_id = "PROMOTION_LETHAL_OVERRIDE"
                return max(winning)[1]
        known_damage = ctx["observed_opponent_damage"]
        current = truth.active
        current_is_one_prize = bool(current and prize_value(current.card_id) == 1)
        ranked: list[tuple[tuple[int, ...], int]] = []
        for option, value in candidates:
            ready = self._pokemon_attack_ready(value, ctx)
            multi_prize = prize_value(value.card_id) > 1
            known_lethal = known_damage > 0 and known_damage >= value.current_hp
            forbidden_unready_ex = bool(current_is_one_prize and multi_prize and not ready and known_lethal)
            score = (
                int(not forbidden_unready_ex),
                int(ready),
                int(not known_lethal),
                -prize_value(value.card_id),
                value.total_energy_units,
                value.current_hp,
                -value.serial,
            )
            ranked.append((score, option.action_index))
        chosen = max(ranked, default=((0,), -1))[1]
        if chosen >= 0:
            self.last_runner_id = "PRIZE_AWARE_ACTIVE_SELECTION"
            return chosen
        return None

    def _plan_for_option(self, index: int, ctx: dict):
        result = super()._plan_for_option(index, ctx)
        option: MewtwoOption = self._option(ctx, index)
        truth: MewtwoTruth = ctx["truth"]
        if option.action_type == T_ATTACK:
            pair = self._pair_key(option, ctx)
            damage = self._attack_option_damage(option, ctx)
            target = truth.opponent_active
            immediate_ko = bool(target and damage >= target.current_hp > 0)
            if pair in self.nonpersistent_attack_pairs and not immediate_ko:
                result.plan.plan_id = "REJECT_NONPERSISTENT_DAMAGE"
                result.illegal = True
                result.regret = max(result.regret, 5000.0)
                result.opponent_pain = 0.0
                result.confidence = 0.99
            active = ctx["active"]
            known_damage = ctx["observed_opponent_damage"]
            expected_counter_ko = bool(active and known_damage > 0 and known_damage >= active.current_hp)
            if expected_counter_ko and not immediate_ko and not ctx["backup_attacker_ready"]:
                result.plan.plan_id = "ATTACK_WITHOUT_BACKUP"
                result.regret = max(result.regret, 1400.0)
                result.hostile_survival = min(result.hostile_survival, 0.12)
                result.opponent_attacks_to_win = 1
        if ctx["deck_clock_critical"] and option.action_type == T_PLAY and option.card_id in LONG_HORIZON_RESOURCE_CARDS:
            result.plan.plan_id = "DECK_CLOCK_SUPPRESS_RESOURCE"
            result.illegal = True
            result.regret = max(result.regret, 4000.0)
            result.opponent_pain = 0.0
            result.confidence = 0.99
        if option.action_type == T_END:
            result.regret = max(result.regret, 2500.0 if self._terminal_attack(ctx) is not None else result.regret)
        return result

    def choose_single(self, options: list, context: dict) -> int:
        terminal = self._terminal_attack(context)
        if terminal is not None:
            self.last_runner_id = "TERMINAL_ACTION_FREEZE"
            chosen = terminal
        else:
            promotion = self._promotion_choice(context)
            chosen = promotion if promotion is not None else super().choose_single(options, context)
        truth: MewtwoTruth = context["truth"]
        if 0 <= chosen < len(truth.options):
            option = truth.options[chosen]
            if option.action_type == T_ATTACK:
                active = truth.active
                target = truth.opponent_active
                if active is not None and target is not None:
                    self._pending_attack = (
                        active.card_id,
                        option.attack_id,
                        target.serial,
                        target.card_id,
                        target.current_hp,
                        truth.turn,
                    )
        return chosen

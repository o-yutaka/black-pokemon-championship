from __future__ import annotations

from typing import Any

from .policy import (
    AZELF,
    BOSS,
    CINDERACE,
    CRISPIN,
    DRAKLOAK,
    DRAGAPULT_EX,
    FIRE_ENERGY,
    DUSCLOPS,
    DUSKNOIR,
    PHANTOM_DIVE,
    PRIME_CATCHER,
    PSYCHIC_ENERGY,
    SWITCH,
    T_ABILITY,
    T_ATTACK,
    T_END,
    T_EVOLVE,
    T_PLAY,
    T_RETREAT,
    _resolved_card,
)
from .policy import DragapultPolicy
from .support import option_attack_id
from .worldline import CandidatePlan, CausalJudge, WorldlineResult, build_board_vision
from .worldline.model import PendingPlan, PlanStep
from .worldline.pending import PendingPlanStore

CTX_SWITCH, CTX_TO_ACTIVE = 3, 4


def _remaining_prizes(player: dict[str, Any]) -> int | None:
    for key in ("prizeCount", "remainingPrizeCount", "remainingPrizes"):
        value = player.get(key)
        if type(value) is int:
            return max(0, value)
    prizes = player.get("prize")
    return len(prizes) if isinstance(prizes, list) else None


def _player(ctx: dict, index: int) -> dict[str, Any]:
    players = ctx["current"].get("players") if isinstance(ctx["current"], dict) else None
    if not isinstance(players, list) or not 0 <= index < len(players):
        return {}
    value = players[index]
    return value if isinstance(value, dict) else {}


class DragapultWorldlinePolicy(DragapultPolicy):
    """Plan-first wrapper around the proven legal-action scorer."""

    def __init__(self) -> None:
        super().__init__()
        self.judge = CausalJudge()
        self.pending = PendingPlanStore()
        self.last_runner_id = "BOOT"

    def build_context(self, obs: dict) -> dict:
        ctx = super().build_context(obs)
        vision = build_board_vision(obs)
        mine = _player(ctx, ctx["me"])
        theirs = _player(ctx, ctx["opp"])
        ctx.update(
            {
                "vision": vision,
                "our_prizes": _remaining_prizes(mine),
                "opponent_prizes": _remaining_prizes(theirs),
                "active_serial": vision.active_serial,
                "opponent_active_serial": vision.opponent_active_serial,
                "turn": int((ctx["current"] or {}).get("turn", (ctx["current"] or {}).get("turnCount", 0)) or 0),
                "ready_bench_dragapult_serials": tuple(
                    ref.serial
                    for ref in vision.mine
                    if ref.area == 5
                    and ref.card_id == DRAGAPULT_EX
                    and FIRE_ENERGY in ref.energy_card_ids
                    and PSYCHIC_ENERGY in ref.energy_card_ids
                ),
            }
        )
        return ctx

    def _base_score(self, option: dict, ctx: dict) -> float:
        return float(super().score_option(option, ctx))

    def _is_dragapult_energy_incomplete(self, ctx: dict) -> bool:
        return bool(ctx["dragapult_lines"]) and not ctx["dragapult_ready"]

    def _bomb_final_prize_loss(self, ctx: dict) -> bool:
        remaining = ctx.get("opponent_prizes")
        return remaining is not None and remaining <= 1

    def _immediate_prize_pressure(self, ctx: dict) -> bool:
        hp = int(ctx.get("opp_hp", 0) or 0)
        if 0 < hp <= 200:
            return True
        return any(0 < int(value.get("hp", 0) or 0) <= 60 for value in ctx["theirs"])

    def _plan_for_option(self, index: int, option: dict, ctx: dict) -> WorldlineResult:
        kind = option.get("type")
        cid = _resolved_card(option, ctx)
        attack_id = option_attack_id(option)
        base = self._base_score(option, ctx)
        plan_id = "SAFE_LEGAL"
        immediate_loss = False
        guaranteed_win = False
        prevents_forced_loss = False
        our_attacks = 4
        opponent_attacks = 1
        hostile_survival = 0.35
        irreversible_cost = 0.0
        pain = max(0.0, base / 10.0)
        regret = max(0.0, 2200.0 - base)
        confidence = 0.60

        if kind == T_ABILITY and cid == DRAKLOAK:
            plan_id = "DRAKLOAK_BEFORE_EVOLVE"
            our_attacks = 2
            hostile_survival = 0.85
            pain = 260.0
            confidence = 0.95
        elif kind == T_ABILITY and cid in {DUSCLOPS, DUSKNOIR}:
            blast = 50 if cid == DUSCLOPS else 130
            plan_id = f"BOMB_{blast}_WORLDLINE"
            immediate_loss = self._bomb_final_prize_loss(ctx)
            lethal_target = any(0 < int(value.get("hp", 0) or 0) <= blast for value in ctx["theirs"])
            phantom_combo = ctx["dragapult_ready"] and 0 < ctx["opp_hp"] <= blast + 200
            azelf_combo = ctx["azelf_ready"] and 10 + ctx["opp_damage"] + blast >= ctx["opp_hp"] > 0
            guaranteed_win = bool(lethal_target and ctx.get("our_prizes") == 1)
            our_attacks = 0 if guaranteed_win else 1 if phantom_combo or azelf_combo else 3
            opponent_attacks = 2 if lethal_target or phantom_combo else 1
            hostile_survival = 0.90 if lethal_target else 0.70 if phantom_combo else 0.20
            irreversible_cost = 1.0
            pain = 900.0 if lethal_target else 650.0 if phantom_combo else 80.0
            regret = 0.0 if lethal_target or phantom_combo or azelf_combo else 900.0
            confidence = 0.95 if lethal_target else 0.80
        elif kind == T_ATTACK and attack_id == PHANTOM_DIVE:
            plan_id = "PHANTOM_200_PLUS_60"
            guaranteed_win = 0 < ctx["opp_hp"] <= 200 and ctx.get("our_prizes") == 1
            our_attacks = 0 if guaranteed_win else 1 if self._immediate_prize_pressure(ctx) else 2
            opponent_attacks = 2 if ctx["ready_count"] >= 2 else 1
            hostile_survival = 0.92
            pain = 800.0 + 120.0 * min(3, ctx["opp_bench"])
            confidence = 0.98
        elif kind == T_ATTACK and ctx["active_id"] == CINDERACE:
            plan_id = "CINDERACE_SETUP"
            missing = sum(
                int(2 > len(value.get("energyCards") or []))
                for value in ctx["dragapult_lines"]
                if isinstance(value, dict)
            )
            our_attacks = 2
            opponent_attacks = 2
            hostile_survival = 0.78 if missing else 0.35
            irreversible_cost = 0.15
            pain = 260.0
            regret = 0.0 if missing else 500.0
        elif kind == T_PLAY and cid == CRISPIN:
            plan_id = "CRISPIN_ENERGY_COMPLETION"
            incomplete = self._is_dragapult_energy_incomplete(ctx)
            our_attacks = 1 if incomplete else 3
            opponent_attacks = 2 if incomplete else 1
            hostile_survival = 0.88 if incomplete else 0.30
            pain = 400.0 if incomplete else 40.0
            regret = 0.0 if incomplete else 600.0
            confidence = 0.90
        elif kind == T_PLAY and cid in {BOSS, PRIME_CATCHER}:
            plan_id = "GUST_PRIZE_ROUTE"
            attack_ready = ctx["dragapult_ready"] or ctx["azelf_ready"]
            immediate_pressure = self._immediate_prize_pressure(ctx)
            our_attacks = 1 if attack_ready and immediate_pressure else 4
            opponent_attacks = 2 if attack_ready and immediate_pressure else 1
            hostile_survival = 0.82 if attack_ready and immediate_pressure else 0.10
            irreversible_cost = 0.85
            pain = 750.0 if attack_ready and immediate_pressure else 20.0
            regret = 0.0 if attack_ready and immediate_pressure else 1000.0
            confidence = 0.82
        elif kind == T_RETREAT or (kind == T_PLAY and cid == SWITCH):
            plan_id = "CINDERACE_HANDOFF"
            allowed = (
                ctx["active_id"] == CINDERACE
                and ctx["dragapult_ready"]
                and self._immediate_prize_pressure(ctx)
            )
            our_attacks = 1 if allowed else 5
            opponent_attacks = 2 if allowed else 1
            hostile_survival = 0.86 if allowed else 0.05
            irreversible_cost = 0.30 if allowed else 1.0
            pain = 620.0 if allowed else 0.0
            regret = 0.0 if allowed else 1200.0
            confidence = 0.90
        elif kind == T_EVOLVE and cid == DRAGAPULT_EX:
            plan_id = "EVOLVE_DRAGAPULT_AFTER_DIRECTIVE"
            drakloak_ability_exists = any(
                isinstance(candidate, dict)
                and candidate.get("type") == T_ABILITY
                and _resolved_card(candidate, ctx) == DRAKLOAK
                for candidate in ctx["select"].get("option", [])
            )
            our_attacks = 3 if drakloak_ability_exists else 1
            hostile_survival = 0.20 if drakloak_ability_exists else 0.82
            regret = 900.0 if drakloak_ability_exists else 0.0
            confidence = 0.90
        elif kind == T_END:
            plan_id = "END_ONLY_WHEN_NO_ROUTE"
            our_attacks = 6
            hostile_survival = 0.01
            regret = 1500.0
            confidence = 0.99

        return WorldlineResult(
            plan=CandidatePlan(
                plan_id=plan_id,
                goal="minimize our prize clock after opponent best response",
                root_action_index=index,
                abort_conditions=("illegal_transition", "target_serial_changed"),
                evidence=(f"legacy_score={base}",),
            ),
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
            metadata={"legacy_score": base, "card_id": cid, "option_type": kind},
        )

    @staticmethod
    def _option_serial(option: dict, ctx: dict) -> int | None:
        player_index = option.get("playerIndex", ctx["me"])
        if type(player_index) is not int:
            player_index = ctx["me"]
        area = option.get("inPlayArea", option.get("area"))
        slot = option.get("inPlayIndex", option.get("index"))
        if type(area) is not int or type(slot) is not int or area not in {4, 5}:
            return None
        players = ctx["current"].get("players") if isinstance(ctx["current"], dict) else None
        if not isinstance(players, list) or not 0 <= player_index < len(players):
            return None
        player = players[player_index] if isinstance(players[player_index], dict) else {}
        zone = player.get("active" if area == 4 else "bench")
        if not isinstance(zone, list) or not 0 <= slot < len(zone) or not isinstance(zone[slot], dict):
            return None
        serial = zone[slot].get("serial")
        return serial if type(serial) is int else None

    def _pending_choice(self, options: list, ctx: dict) -> int | None:
        pending = self.pending.get()
        if pending is None:
            return None
        bound_turn = pending.bindings.get("turn")
        if type(bound_turn) is int and bound_turn != ctx.get("turn"):
            self.pending.invalidate("turn_changed")
            return None
        step = pending.step
        if step is None:
            self.pending.clear()
            return None
        for index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            kind = option.get("type")
            cid = _resolved_card(option, ctx)
            if step.expected_type is not None and kind != step.expected_type:
                continue
            if step.card_id is not None and cid != step.card_id:
                continue
            if step.attack_id is not None and option_attack_id(option) != step.attack_id:
                continue
            if step.target_serial is not None and self._option_serial(option, ctx) != step.target_serial:
                continue
            pending.advance()
            self.last_runner_id = f"PENDING:{pending.candidate.plan_id}:{step.name}"
            if pending.status == "COMPLETE":
                self.pending.clear()
            return index
        return None

    def _reserve_handoff(self, chosen: WorldlineResult, option: dict, ctx: dict) -> None:
        if chosen.plan.plan_id != "CINDERACE_HANDOFF":
            return
        if _resolved_card(option, ctx) != SWITCH:
            return
        serials = ctx.get("ready_bench_dragapult_serials") or ()
        if not serials:
            return
        serial = int(serials[0])
        candidate = CandidatePlan(
            plan_id="SWITCH_HANDOFF_PHANTOM",
            goal="move the exact ready Dragapult active and complete Phantom Dive",
            root_action_index=chosen.plan.root_action_index,
            steps=(
                PlanStep(name="select_ready_dragapult", target_serial=serial),
                PlanStep(name="attack_phantom", expected_type=T_ATTACK, card_id=DRAGAPULT_EX, attack_id=PHANTOM_DIVE),
            ),
            reserved_serials=(serial,),
            reserved_card_ids=(SWITCH, DRAGAPULT_EX),
            abort_conditions=("target_serial_missing", "turn_changed", "phantom_unavailable"),
            evidence=(f"ready_dragapult_serial={serial}",),
        )
        self.pending.set(PendingPlan(candidate=candidate, bindings={"turn": int(ctx.get("turn", 0))}))

    def choose_single(self, options: list, context: dict) -> int:
        pending = self._pending_choice(options, context)
        if pending is not None:
            return pending
        results = [
            self._plan_for_option(index, option, context)
            for index, option in enumerate(options)
            if isinstance(option, dict)
        ]
        chosen = self.judge.choose(results)
        self.last_runner_id = chosen.plan.plan_id
        chosen_option = options[chosen.plan.root_action_index]
        if isinstance(chosen_option, dict):
            self._reserve_handoff(chosen, chosen_option, context)
        return chosen.plan.root_action_index

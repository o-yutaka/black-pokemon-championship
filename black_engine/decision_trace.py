from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_DISCARD, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 11, 12, 13, 14
SWITCH_CARD_ID = 1123
CINDERACE = 666
DUSK_LINE = {131, 132, 133}

ACTION_NAMES = {
    T_PLAY: "PLAY",
    T_ENERGY: "ENERGY",
    T_EVOLVE: "EVOLVE",
    T_ABILITY: "ABILITY",
    T_DISCARD: "DISCARD",
    T_RETREAT: "RETREAT",
    T_ATTACK: "ATTACK",
    T_END: "END",
}

POLICY_NAMES = {
    T_PLAY: "TrainerPolicy",
    T_ENERGY: "EnergyPolicy",
    T_EVOLVE: "EvolutionPolicy",
    T_ABILITY: "AbilityPolicy",
    T_DISCARD: "ResourcePolicy",
    T_RETREAT: "SwitchLoopPolicy",
    T_ATTACK: "AttackPolicy",
    T_END: "ClockPolicy",
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _integer(value: Any, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _card_id(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        for key in ("cardId", "card", "id", "pokemonId"):
            raw = value.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool):
                return raw
    return -1


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _resolve_card(option: Mapping[str, Any], context: Mapping[str, Any]) -> int:
    for key in ("card", "cardId", "id"):
        cid = _card_id(option.get(key))
        if cid >= 0:
            return cid
    current = _mapping(context.get("current"))
    players = _sequence(current.get("players"))
    player_index = _integer(option.get("playerIndex"), _integer(context.get("me"), 0))
    player = _mapping(players[player_index]) if 0 <= player_index < len(players) else {}
    area = option.get("area")
    if area is None and _integer(option.get("type")) == T_PLAY:
        area = 2
    zone_key = {1: "deck", 2: "hand", 3: "discard", 4: "active", 5: "bench", 6: "prize", 12: "looking"}.get(area)
    index = _integer(option.get("index"))
    values = _sequence(player.get(zone_key)) if zone_key else []
    if 0 <= index < len(values):
        return _card_id(values[index])
    return -1


def _resolve_target(option: Mapping[str, Any], context: Mapping[str, Any]) -> int:
    for key in ("target", "pokemon", "to", "selectPokemon"):
        cid = _card_id(option.get(key))
        if cid >= 0:
            return cid
    current = _mapping(context.get("current"))
    players = _sequence(current.get("players"))
    player_index = _integer(option.get("playerIndex"), _integer(context.get("me"), 0))
    player = _mapping(players[player_index]) if 0 <= player_index < len(players) else {}
    area = option.get("inPlayArea", option.get("area"))
    index = _integer(option.get("inPlayIndex", option.get("index")))
    zone_key = {4: "active", 5: "bench"}.get(area)
    values = _sequence(player.get(zone_key)) if zone_key else []
    if 0 <= index < len(values):
        return _card_id(values[index])
    return -1


def option_label(index: int, option: Any, context: Mapping[str, Any]) -> str:
    raw = _mapping(option)
    action_type = _integer(raw.get("type"))
    name = ACTION_NAMES.get(action_type, f"TYPE_{action_type}")
    cid = _resolve_card(raw, context)
    target = _resolve_target(raw, context)
    attack = _integer(raw.get("attackId"))
    parts = [f"[{index}] {name}"]
    if cid >= 0:
        parts.append(f"card#{cid}")
    if target >= 0 and target != cid:
        parts.append(f"target#{target}")
    if attack >= 0:
        parts.append(f"attack#{attack}")
    return " · ".join(parts)


def selected_action(index: int, option: Any, context: Mapping[str, Any]) -> dict[str, Any]:
    raw = _mapping(option)
    action_type = _integer(raw.get("type"))
    resolved = _resolve_card(raw, context)
    return {
        "arrayIndex": 0,
        "optionIndex": index,
        "kind": ACTION_NAMES.get(action_type, f"TYPE_{action_type}"),
        "cardId": resolved if resolved >= 0 else None,
        "serial": raw.get("serial", raw.get("instanceSerial")),
        "effectSource": str(raw.get("effectSource", raw.get("sourceName", "")) or ""),
        "label": option_label(index, raw, context),
    }


def direct_branch_rejection(option: Any, context: Mapping[str, Any], score: float, *, best_non_end: float | None = None) -> dict[str, Any] | None:
    raw = _mapping(option)
    action_type = _integer(raw.get("type"))
    cid = _resolve_card(raw, context)
    target = _resolve_target(raw, context)
    active_id = _integer(context.get("active_id"))
    dragapult_ready = bool(context.get("dragapult_ready"))

    if action_type == T_RETREAT and not (active_id == CINDERACE and dragapult_ready):
        return {
            "reason": "RESOURCE_LOSS_CYCLE",
            "evidence": {
                "state_before": _hash(context.get("current", {})),
                "same_active_expected": True,
                "attack_delta": 0,
                "prize_delta": 0,
                "energy_delta": -1,
                "retreat_used": True,
                "active_id": active_id,
                "dragapult_ready": dragapult_ready,
            },
            "metrics": {"energy": -1, "tempo": -1, "prize": 0},
            "killedBy": "SwitchLoopPolicy",
            "source": "ScoredPolicy.choose_single",
        }
    if action_type == T_PLAY and cid == SWITCH_CARD_ID and not (active_id == CINDERACE and dragapult_ready):
        return {
            "reason": "RESOURCE_LOSS_CYCLE",
            "evidence": {
                "state_before": _hash(context.get("current", {})),
                "same_active_expected": True,
                "attack_delta": 0,
                "prize_delta": 0,
                "trainer_delta": -1,
                "active_id": active_id,
                "dragapult_ready": dragapult_ready,
            },
            "metrics": {"trainer": -1, "tempo": -1, "prize": 0},
            "killedBy": "SwitchLoopPolicy",
            "source": "ScoredPolicy.choose_single",
        }
    if action_type == T_ENERGY and target in DUSK_LINE:
        return {
            "reason": "ENERGY_WRONG_TARGET",
            "evidence": {"target_card_id": target, "dragapult_ready": dragapult_ready, "score": score},
            "metrics": {"energy": -1, "futureAttack": -1},
            "killedBy": "EnergyPolicy",
            "source": "ScoredPolicy.choose_single",
        }
    if action_type == T_ABILITY and cid in {132, 133} and score < 0:
        return {
            "reason": "SELF_KO_NO_PRIZE_ROUTE",
            "evidence": {"ability_card_id": cid, "score": score, "opponent_hp": context.get("opp_hp")},
            "metrics": {"selfPrize": -1, "prize": 0},
            "killedBy": "BombRoutePolicy",
            "source": "ScoredPolicy.choose_single",
        }
    if action_type == T_END and best_non_end is not None and best_non_end > score and best_non_end > 0:
        return {
            "reason": "PREMATURE_END",
            "evidence": {"end_score": score, "best_available_score": best_non_end},
            "metrics": {"tempo": score - best_non_end},
            "killedBy": "ClockPolicy",
            "source": "ScoredPolicy.choose_single",
        }
    return None


def _route_and_prize(obs: Mapping[str, Any], context: Mapping[str, Any], chosen: str) -> tuple[dict[str, Any], dict[str, Any]]:
    current = _mapping(obs.get("current"))
    players = _sequence(current.get("players"))
    me = _integer(context.get("me"), 0)
    mine = _mapping(players[me]) if 0 <= me < len(players) else {}
    prize_count = _integer(mine.get("prizeCount"), len(_sequence(mine.get("prize"))))
    ready = bool(context.get("dragapult_ready"))
    azelf_ready = bool(context.get("azelf_ready"))
    attack_capacity = 2 if ready else 1
    needed_attacks = max(0, (prize_count + attack_capacity - 1) // attack_capacity)
    route_steps = [
        {"label": f"Current prizes remaining: {prize_count}", "status": "current"},
        {"label": chosen, "status": "selected"},
        {"label": "Dragapult attack route" if ready else "Build attack-ready Dragapult", "status": "ready" if ready else "pending"},
        {"label": "Azelf terminal available" if azelf_ready else "Azelf terminal unavailable", "status": "ready" if azelf_ready else "pending"},
    ]
    route = {
        "name": "Dragapult Prize Route",
        "current": 1 + int(ready),
        "total": len(route_steps),
        "steps": route_steps,
        "source": "live observation + policy context",
    }
    planner = {
        "neededAttacks": needed_attacks,
        "remainingPrizes": prize_count,
        "attackPrizeCapacity": attack_capacity,
        "dragapultReady": ready,
        "azelfReady": azelf_ready,
        "risk": None,
        "source": "actual prize count; future attacks are policy-route estimates",
    }
    return route, planner


def _board_analysis(context: Mapping[str, Any]) -> dict[str, Any]:
    ready_count = _integer(context.get("ready_count"), 0)
    opponent_damage = _integer(context.get("opp_damage"), 0)
    bench_slots = _integer(context.get("bench_slots"), 0)
    deck_count = _integer(context.get("deck_count"), 0)
    energy = 20 + 22 * ready_count
    tempo = 12 + 18 * int(bool(context.get("dragapult_ready")))
    bench_value = max(0, 20 - 3 * bench_slots)
    damage = min(30, opponent_damage / 10)
    draw = min(20, deck_count / 3)
    future = 12 * int(bool(context.get("azelf_ready")))
    return {
        "total": round(energy + tempo + bench_value + damage + draw + future, 2),
        "components": {
            "energy": energy,
            "tempo": tempo,
            "bench": bench_value,
            "damage": damage,
            "draw": draw,
            "future": future,
        },
        "threatMap": [],
        "source": "current policy context",
    }


def build_decision_overlay(
    *,
    obs: Mapping[str, Any],
    context: Mapping[str, Any],
    options: Sequence[Any],
    selection: Sequence[int],
    scores: Sequence[float],
    rejections: Sequence[Mapping[str, Any]],
    search_report: Mapping[str, Any],
    decision_diff: Mapping[str, Any] | None,
    decision_id: str,
    elapsed_ms: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    selected_index = selection[0] if len(selection) == 1 and isinstance(selection[0], int) and 0 <= selection[0] < len(options) else None
    selected = selected_action(selected_index, options[selected_index], context) if selected_index is not None else None
    chosen = selected["label"] if selected else str(list(selection))
    candidates = []
    for index, option in enumerate(options):
        resolved = _resolve_card(_mapping(option), context)
        candidates.append({
            "label": option_label(index, option, context),
            "score": float(scores[index]) if index < len(scores) else 0.0,
            "selected": index in selection,
            "kind": ACTION_NAMES.get(_integer(_mapping(option).get("type")), "UNKNOWN"),
            "cardId": resolved if resolved >= 0 else None,
        })
    priority = [row["label"] for row in sorted(candidates, key=lambda row: row["score"], reverse=True)[:4]]
    rejection_map = {int(item.get("optionIndex", -1)): dict(item) for item in rejections if isinstance(item.get("optionIndex"), int)}
    policy_trace = []
    for index, option in enumerate(options):
        action_type = _integer(_mapping(option).get("type"))
        rejection = rejection_map.get(index)
        policy_trace.append({
            "policy": POLICY_NAMES.get(action_type, "RoutePolicy"),
            "action": option_label(index, option, context),
            "status": "PASS" if index in selection else "FAIL" if rejection else "HOLD",
            "score": float(scores[index]) if index < len(scores) else 0.0,
            "reason": rejection.get("reason") if rejection else "score_option",
            "source": rejection.get("source") if rejection else "DragapultPolicy.score_option",
        })

    search_tree = _mapping(search_report.get("searchTree"))
    search_rejections = [dict(item) for item in _sequence(search_report.get("rejectedBranches")) if isinstance(item, Mapping)]
    all_rejections = [dict(item) for item in rejections] + search_rejections
    counterfactuals = [dict(item) for item in _sequence(search_report.get("counterfactuals")) if isinstance(item, Mapping)]
    route, prize_planner = _route_and_prize(obs, context, chosen)
    selected_score = float(scores[selected_index]) if selected_index is not None and selected_index < len(scores) else 0.0
    scores_payload: dict[str, float] = {"policy": selected_score, "total": selected_score}
    selected_search = next((item for item in counterfactuals if item.get("selected")), None)
    if selected_search and selected_search.get("expectedValue") is not None:
        scores_payload["search"] = _number(selected_search.get("expectedValue"))

    warnings: list[str] = []
    if search_report.get("enabled") is False and search_report.get("reason"):
        warnings.append(f"Search trace unavailable: {search_report['reason']}")
    warnings.extend(str(error) for error in _sequence(search_report.get("errors"))[:3])

    current = _mapping(obs.get("current"))
    truth_ledger = {
        "decisionId": decision_id,
        "truth": "PASS",
        "evidenceCount": len(candidates) + len(all_rejections),
        "policy": "DragapultPolicy",
        "engine": "official observation",
        "search": "PASS" if search_report.get("enabled") else "UNAVAILABLE",
        "stateHash": _hash(current),
        "selectHash": _hash(obs.get("select")),
        "searchSource": search_report.get("source"),
        "reason": search_report.get("reason", ""),
    }
    causality_graph = {
        "nodes": [
            {"id": "selected", "label": chosen},
            {"id": "route", "label": "Prize Route"},
            {"id": "future", "label": "Future Attack"},
        ],
        "edges": [
            {"from": "selected", "to": "route", "label": "changes"},
            {"from": "route", "to": "future", "label": "enables"},
        ],
        "source": "selected action + live route state",
    }
    heatmap = {row["label"]: row["score"] for row in candidates}
    policy_battle = [{"policy": row["policy"], "score": row["score"], "status": row["status"]} for row in policy_trace]
    overlay = {
        "schemaVersion": "2.0",
        "decisionId": decision_id,
        "goal": "2T Dragapult Attack" if not context.get("dragapult_ready") else "Convert attack-ready board into prizes",
        "priority": priority,
        "chosen": chosen,
        "confidence": None,
        "elapsedMs": elapsed_ms,
        "selectedAction": selected,
        "selectedActions": [selected_action(index, options[index], context) for index in selection if isinstance(index, int) and 0 <= index < len(options)],
        "scores": scores_payload,
        "flags": {
            "abilityUsed": bool(selected and selected.get("kind") == "ABILITY"),
            "lethal": bool(context.get("opp_hp") and context.get("opp_hp") <= 200 and selected and selected.get("kind") == "ATTACK"),
            "waste": any(item.get("optionIndex") == selected_index for item in all_rejections),
        },
        "warnings": warnings,
        "candidates": candidates,
        "alternatives": [row for row in candidates if not row["selected"]],
        "scoreSource": "agent_policy_and_official_search" if search_report.get("enabled") else "agent_policy",
        "searchTree": search_tree,
        "rejectedBranches": all_rejections,
        "policyTrace": policy_trace,
        "boardAnalysis": _board_analysis(context),
        "route": route,
        "prizePlanner": prize_planner,
        "heatmap": heatmap,
        "policyBattle": policy_battle,
        "counterfactuals": counterfactuals,
        "causalityGraph": causality_graph,
        "hiddenBelief": _mapping(search_report.get("hiddenBelief")),
        "decisionDiff": dict(decision_diff) if decision_diff else None,
        "truthLedger": truth_ledger,
    }
    prediction = _mapping(search_report.get("selectedPrediction")) or None
    if prediction is not None:
        prediction["decisionId"] = decision_id
    return overlay, prediction

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _seq(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _card(raw: Mapping[str, Any], player: int, zone: str, slot: int | None) -> dict[str, Any]:
    card_id = _int(raw.get("cardId", raw.get("card_id", raw.get("id"))))
    serial = _int(raw.get("serial", raw.get("instanceSerial")))
    max_hp = raw.get("maxHp", raw.get("max_hp"))
    hp = raw.get("hp", raw.get("currentHp", raw.get("current_hp")))
    max_hp_int = None if max_hp is None else _int(max_hp)
    hp_int = None if hp is None else _int(hp)
    damage_raw = raw.get("damage", raw.get("damageCounter", raw.get("damage_counter")))
    damage = _int(damage_raw, max(0, (max_hp_int or 0) - (hp_int or 0)))
    energies = [str(item.get("name", item.get("id", "?"))) if isinstance(item, Mapping) else str(item) for item in _seq(raw.get("energyCards", raw.get("energies", [])))]
    tools = [str(item.get("name", item.get("id", "?"))) if isinstance(item, Mapping) else str(item) for item in _seq(raw.get("tools", []))]
    evolution = [_int(item.get("id", item.get("cardId"))) if isinstance(item, Mapping) else _int(item) for item in _seq(raw.get("preEvolution", raw.get("evolution", [])))]
    status = [str(item) for item in _seq(raw.get("status", raw.get("statuses", [])))]
    return {"playerIndex": player, "serial": serial, "cardId": card_id, "name": str(raw.get("name", f"Card #{card_id}")), "zone": zone, "slot": slot, "hp": hp_int, "maxHp": max_hp_int, "damage": max(0, damage), "energies": energies, "tools": tools, "status": status, "evolution": evolution, "imageUrl": None}


def _visible_cards(value: Any, player: int, zone: str, limit: int | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for slot, item in enumerate(_seq(value)):
        if limit is not None and len(result) >= limit:
            break
        if not isinstance(item, Mapping) or item.get("serial") is None or item.get("id", item.get("cardId")) is None:
            continue
        result.append(_card(item, player, zone, slot))
    return result


def _player(raw: Mapping[str, Any], player: int) -> dict[str, Any]:
    active_items = _visible_cards(raw.get("active", raw.get("activePokemon", [])), player, "active", 1)
    bench = _visible_cards(raw.get("bench", raw.get("benchPokemon", [])), player, "bench", 5)
    hand = _visible_cards(raw.get("hand", []), player, "hand")
    discard = _visible_cards(raw.get("discard", raw.get("discardPile", [])), player, "discard")
    return {"name": str(raw.get("name", raw.get("playerName", f"Player {player + 1}"))), "active": active_items[0] if active_items else None, "bench": bench, "hand": hand, "handCount": max(_int(raw.get("handCount"), len(hand)), len(hand)), "deckCount": max(0, _int(raw.get("deckCount"), len(_seq(raw.get("deck", []))))), "prizeCount": max(0, _int(raw.get("prizeCount"), len(_seq(raw.get("prize", raw.get("prizes", [])))))), "discard": discard, "supporterPlayed": bool(raw.get("supporterPlayed", False)), "retreated": bool(raw.get("retreated", raw.get("retreatUsed", False)))}


def _result(value: Any) -> str | None:
    if value is None or value in {-1, "-1", "", "ongoing", "ONGOING"}:
        return None
    if value in {0, "0"}:
        return "P0_WIN"
    if value in {1, "1"}:
        return "P1_WIN"
    if value in {2, "2"}:
        return "DRAW"
    return str(value)


def _candidate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, Any] = {"label": str(value.get("label", value.get("name", "候補"))), "score": float(value.get("score", 0.0) or 0.0), "selected": bool(value.get("selected", False))}
    for key in ("reason", "kind"):
        if value.get(key) is not None:
            result[key] = str(value[key])
    for key in ("cardId", "serial"):
        if value.get(key) is not None:
            result[key] = _int(value[key])
    return result


def _decision(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or value.get("actor") not in (0, 1):
        return None
    candidates = [candidate for item in _seq(value.get("candidates")) if (candidate := _candidate(item)) is not None]
    alternatives = [candidate for item in _seq(value.get("alternatives")) if (candidate := _candidate(item)) is not None]
    selected_action = dict(value["selectedAction"]) if isinstance(value.get("selectedAction"), Mapping) else None
    selected_actions = [dict(item) for item in _seq(value.get("selectedActions")) if isinstance(item, Mapping)]
    scores = {str(key): float(item) for key, item in dict(value.get("scores", {})).items() if isinstance(item, (int, float)) and not isinstance(item, bool)} if isinstance(value.get("scores"), Mapping) else {}
    flags = {str(key): bool(item) for key, item in dict(value.get("flags", {})).items()} if isinstance(value.get("flags"), Mapping) else {}
    confidence = value.get("confidence")
    return {
        "actor": int(value["actor"]),
        "goal": str(value.get("goal", "uploaded_bundle_agent")),
        "chosen": str(value.get("chosen", "[]")),
        "confidence": float(confidence) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else None,
        "elapsedMs": float(value["elapsedMs"]) if isinstance(value.get("elapsedMs"), (int, float)) and not isinstance(value.get("elapsedMs"), bool) else None,
        "candidates": candidates,
        "overlayVersion": str(value.get("overlayVersion", value.get("schemaVersion", "1.0"))),
        "selectedAction": selected_action,
        "selectedActions": selected_actions,
        "scores": scores,
        "flags": flags,
        "warnings": [str(item) for item in _seq(value.get("warnings"))],
        "alternatives": alternatives,
        "boardDiff": [str(item) for item in _seq(value.get("boardDiff"))],
        "scoreSource": str(value.get("scoreSource", "unknown")),
    }


def normalize_official_frame(raw: Mapping[str, Any], frame_id: int) -> dict[str, Any]:
    state = raw.get("current") if isinstance(raw.get("current"), Mapping) else raw
    players_raw = state.get("players") if isinstance(state, Mapping) else None
    if not isinstance(players_raw, Sequence) or len(players_raw) != 2:
        raise ValueError("official frame requires exactly two players")
    acting = _int(raw.get("actingPlayer", state.get("yourIndex", state.get("playerIndex", 0))))
    if acting not in (0, 1):
        acting = 0
    events = []
    for item in _seq(raw.get("logs", raw.get("events", []))):
        if isinstance(item, Mapping):
            actor_int = _int(item.get("playerIndex", item.get("actor")), -1)
            events.append({"type": str(item.get("type", "log")), "actor": actor_int if actor_int in (0, 1) else None, "text": str(item.get("text", item.get("message", item))), "cardKey": None})
        else:
            events.append({"type": "log", "actor": None, "text": str(item), "cardKey": None})
    return {"frameId": frame_id, "turn": max(0, _int(raw.get("turn", state.get("turn", 0)))), "actionCount": max(0, _int(raw.get("actionCount", state.get("turnActionCount", frame_id)))), "actingPlayer": acting, "phase": "result" if _result(state.get("result")) else str(raw.get("phase", "main")), "players": [_player(players_raw[0], 0), _player(players_raw[1], 1)], "stadium": None, "events": events, "decision": _decision(raw.get("decision")), "result": _result(state.get("result", raw.get("result")))}

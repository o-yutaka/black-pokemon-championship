#!/usr/bin/env python3
"""Convert recorded CABT snapshots into BLACK Battle Studio schema.

The converter is intentionally conservative:
- complete snapshots are the source of truth;
- logs are copied only as presentation events;
- hidden cards are never inferred;
- card identity is playerIndex + serial;
- unsupported shapes fail instead of fabricating a board.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "1.0"
ZONES = {"active", "bench", "hand", "deck", "discard", "prize", "looking", "unknown"}


class ConversionError(ValueError):
    """Raised when an input cannot be safely normalized."""


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConversionError(f"{label} must be an object")
    return value


def _as_sequence(value: Any) -> Sequence[Any]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _first(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return default


def _integer(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _nullable_integer(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nullable_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in _as_sequence(value):
        if isinstance(item, Mapping):
            label = _first(item, "name", "type", "energyType", "cardId", default="")
            result.append(str(label))
        elif item is not None:
            result.append(str(item))
    return result


def normalize_card(raw: Any, player_index: int, zone: str, slot: int | None) -> dict[str, Any]:
    card = _as_mapping(raw, "card")
    serial = _nullable_integer(_first(card, "serial", "instanceSerial"))
    card_id = _nullable_integer(_first(card, "cardId", "card_id", "id"))
    if serial is None or card_id is None:
        raise ConversionError("visible card requires serial and cardId")

    normalized_zone = zone if zone in ZONES else "unknown"
    max_hp = _nullable_integer(_first(card, "maxHp", "max_hp"))
    hp = _nullable_integer(_first(card, "hp", "currentHp", "current_hp"))
    damage = _nullable_integer(_first(card, "damage", "damageCounter", "damage_counter"))
    if damage is None and hp is not None and max_hp is not None:
        damage = max(0, max_hp - hp)

    evolution: list[int] = []
    for item in _as_sequence(_first(card, "preEvolution", "evolution", "evolutionStack", default=[])):
        if isinstance(item, Mapping):
            value = _nullable_integer(_first(item, "cardId", "id"))
        else:
            value = _nullable_integer(item)
        if value is not None:
            evolution.append(value)

    return {
        "playerIndex": player_index,
        "serial": serial,
        "cardId": card_id,
        "name": str(_first(card, "name", "cardName", default=f"Card #{card_id}")),
        "zone": normalized_zone,
        "slot": slot,
        "hp": hp,
        "maxHp": max_hp,
        "damage": max(0, damage or 0),
        "energies": _string_list(_first(card, "energyCards", "energies", default=[])),
        "tools": _string_list(_first(card, "tools", "toolCards", default=[])),
        "status": _string_list(_first(card, "status", "statuses", default=[])),
        "evolution": evolution,
        "imageUrl": None,
    }


def _normalize_cards(
    raw: Any,
    player_index: int,
    zone: str,
    limit: int | None = None,
    *,
    skip_opaque: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for slot, item in enumerate(_as_sequence(raw)):
        if limit is not None and len(result) >= limit:
            break
        if item is None:
            continue
        if skip_opaque:
            if not isinstance(item, Mapping):
                continue
            if _nullable_integer(_first(item, "serial", "instanceSerial")) is None:
                continue
            if _nullable_integer(_first(item, "cardId", "card_id", "id")) is None:
                continue
        result.append(normalize_card(item, player_index, zone, slot))
    return result


def normalize_player(raw: Any, player_index: int) -> dict[str, Any]:
    player = _as_mapping(raw, f"player[{player_index}]")
    active_raw = _first(player, "active", "activePokemon")
    active = normalize_card(active_raw, player_index, "active", 0) if active_raw else None
    bench = _normalize_cards(_first(player, "bench", "benchPokemon", default=[]), player_index, "bench", limit=5)
    hand = _normalize_cards(_first(player, "hand", default=[]), player_index, "hand", skip_opaque=True)
    discard = _normalize_cards(_first(player, "discard", "discardPile", default=[]), player_index, "discard")

    hand_count = _integer(_first(player, "handCount", "hand_count", default=len(hand)), len(hand))
    deck_raw = _first(player, "deck", default=[])
    deck_count = _integer(_first(player, "deckCount", "deck_count", default=len(_as_sequence(deck_raw))), len(_as_sequence(deck_raw)))
    prize_raw = _first(player, "prize", "prizes", default=[])
    prize_count = _integer(_first(player, "prizeCount", "prize_count", default=len(_as_sequence(prize_raw))), len(_as_sequence(prize_raw)))

    return {
        "name": str(_first(player, "name", "playerName", default=f"Player {player_index + 1}")),
        "active": active,
        "bench": bench,
        "hand": hand,
        "handCount": max(hand_count, len(hand)),
        "deckCount": max(0, deck_count),
        "prizeCount": max(0, prize_count),
        "discard": discard,
        "supporterPlayed": bool(_first(player, "supporterPlayed", "supporter_played", default=False)),
        "retreated": bool(_first(player, "retreated", "retreatUsed", default=False)),
    }


def normalize_events(raw: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in _as_sequence(raw):
        if isinstance(item, Mapping):
            actor = _nullable_integer(_first(item, "playerIndex", "actor", "player"))
            if actor not in (0, 1):
                actor = None
            events.append({
                "type": str(_first(item, "type", "logType", default="log")),
                "actor": actor,
                "text": str(_first(item, "text", "message", "description", default=json.dumps(item, ensure_ascii=False))),
                "cardKey": None,
            })
        else:
            events.append({"type": "log", "actor": None, "text": str(item), "cardKey": None})
    return events


def normalize_decision(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    actor = _nullable_integer(_first(raw, "actor", "playerIndex"))
    chosen = _first(raw, "chosen", "selected", "action")
    if actor not in (0, 1) or chosen is None:
        return None

    confidence = _nullable_float(_first(raw, "confidence"))
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        confidence = None
    elapsed_ms = _nullable_float(_first(raw, "elapsedMs", "elapsed_ms", "decisionMs"))
    if elapsed_ms is not None and elapsed_ms < 0:
        elapsed_ms = None

    candidates: list[dict[str, Any]] = []
    for item in _as_sequence(_first(raw, "candidates", default=[])):
        if not isinstance(item, Mapping):
            continue
        label = _first(item, "label", "action", "name")
        score = _nullable_float(_first(item, "score", "value"))
        if label is None or score is None:
            continue
        candidates.append({
            "label": str(label),
            "score": score,
            "selected": bool(_first(item, "selected", default=False)),
        })

    return {
        "actor": actor,
        "goal": str(_first(raw, "goal", default="unrecorded")),
        "chosen": str(chosen),
        "confidence": confidence,
        "elapsedMs": elapsed_ms,
        "candidates": candidates,
    }


def _extract_state(frame: Mapping[str, Any]) -> Mapping[str, Any]:
    current = frame.get("current")
    if isinstance(current, Mapping):
        return current
    observation = frame.get("observation")
    if isinstance(observation, Mapping):
        current = observation.get("current")
        if isinstance(current, Mapping):
            return current
        return observation
    state = frame.get("state")
    if isinstance(state, Mapping):
        return state
    return frame


def normalize_frame(raw: Any, frame_id: int) -> dict[str, Any]:
    frame = _as_mapping(raw, f"frame[{frame_id}]")
    state = _extract_state(frame)
    players = _first(state, "players", default=None)
    if not isinstance(players, Sequence) or isinstance(players, (str, bytes, bytearray)) or len(players) != 2:
        raise ConversionError(f"frame[{frame_id}] must contain exactly two players")

    acting_player = _integer(_first(frame, "actingPlayer", "playerIndex", default=_first(state, "playerIndex", "currentPlayer", default=0)))
    if acting_player not in (0, 1):
        raise ConversionError(f"frame[{frame_id}] has invalid acting player")

    stadium = None
    stadium_raw = _first(state, "stadium")
    if isinstance(stadium_raw, Mapping) and _first(stadium_raw, "serial") is not None:
        stadium_owner = _nullable_integer(_first(stadium_raw, "playerIndex", "owner", "ownerIndex"))
        if stadium_owner in (0, 1):
            stadium = normalize_card(stadium_raw, stadium_owner, "unknown", None)

    return {
        "frameId": frame_id,
        "turn": max(0, _integer(_first(frame, "turn", default=_first(state, "turn", default=0)))),
        "actionCount": max(0, _integer(_first(frame, "actionCount", "step", default=frame_id))),
        "actingPlayer": acting_player,
        "phase": str(_first(frame, "phase", default=_first(state, "phase", default="unknown"))),
        "players": [normalize_player(players[0], 0), normalize_player(players[1], 1)],
        "stadium": stadium,
        "events": normalize_events(_first(frame, "logs", "events", default=[])),
        "decision": normalize_decision(_first(frame, "decision", default=None)),
        "result": _first(frame, "result", default=_first(state, "result", default=None)),
    }


def _extract_frames(payload: Any) -> Iterable[Any]:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return payload
    root = _as_mapping(payload, "root")
    if root.get("schemaVersion") == SCHEMA_VERSION and isinstance(root.get("frames"), list):
        return root["frames"]
    for key in ("frames", "snapshots", "records", "steps"):
        value = root.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return value
    raise ConversionError("input requires frames, snapshots, records, steps, or a top-level array")


def convert(payload: Any, replay_id: str, source: str, hidden_policy: str) -> dict[str, Any]:
    if isinstance(payload, Mapping) and payload.get("schemaVersion") == SCHEMA_VERSION:
        # Preserve an already normalized document without reinterpreting it.
        return dict(payload)

    frames = [normalize_frame(raw, index) for index, raw in enumerate(_extract_frames(payload))]
    if not frames:
        raise ConversionError("input contains no frames")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "replayId": replay_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "hiddenInformationPolicy": hidden_policy,
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--replay-id", default=None)
    parser.add_argument("--source", choices=("cabt", "kaggle", "demo", "unknown"), default="cabt")
    parser.add_argument("--hidden-policy", choices=("player_view", "spectator", "unknown"), default="unknown")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    normalized = convert(payload, args.replay_id or args.input.stem, args.source, args.hidden_policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS frames={len(normalized['frames'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

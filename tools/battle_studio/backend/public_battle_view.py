from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

_PUBLIC_ZONES = {"active", "bench", "hand", "deck", "discard", "prize", "looking", "unknown"}
_PUBLIC_DECISION_KEYS = {"actor", "goal", "chosen", "confidence", "elapsedMs", "warnings"}
_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/)(?:[^\s\]\[{}]+[/\\])+[^\s\]\[{}]*")
_INTERNAL_RE = re.compile(r"\b(?:select(?:ion)?|serial|area|index|context|searchId|battlePtr|libcg|observation)\b", re.IGNORECASE)


def _integer(value: Any, default: int = 0, minimum: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any, default: str = "", limit: int = 240) -> str:
    text = str(value) if value is not None else default
    text = _PATH_RE.sub("[private]", text)
    if _INTERNAL_RE.search(text):
        return "内部処理は非公開です"
    return text[:limit]


def _opaque_serial(secret: bytes, player: int, serial: Any) -> int:
    raw = f"{player}:{serial}".encode("utf-8", errors="replace")
    digest = hmac.new(secret, raw, hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _public_card(card: Any, secret: bytes, player: int, *, reveal_identity: bool = True) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    zone = str(card.get("zone", "unknown"))
    if zone not in _PUBLIC_ZONES:
        zone = "unknown"
    card_id = _integer(card.get("cardId")) if reveal_identity else 0
    name = _text(card.get("name"), "非公開カード") if reveal_identity else "非公開カード"
    image_url = card.get("imageUrl") if reveal_identity and isinstance(card.get("imageUrl"), str) else None
    return {
        "playerIndex": player,
        "serial": _opaque_serial(secret, player, card.get("serial", 0)),
        "cardId": card_id,
        "name": name,
        "zone": zone,
        "slot": _integer(card.get("slot")) if card.get("slot") is not None else None,
        "hp": _integer(card.get("hp")) if card.get("hp") is not None else None,
        "maxHp": _integer(card.get("maxHp")) if card.get("maxHp") is not None else None,
        "damage": _integer(card.get("damage")),
        "energies": [_text(item, limit=48) for item in card.get("energies", []) if isinstance(item, (str, int))][:12],
        "tools": [_text(item, limit=80) for item in card.get("tools", []) if isinstance(item, (str, int))][:8],
        "status": [_text(item, limit=48) for item in card.get("status", []) if isinstance(item, (str, int))][:8],
        "evolution": [_integer(item) for item in card.get("evolution", []) if isinstance(item, int) and not isinstance(item, bool)][:8],
        "imageUrl": image_url,
    }


def _public_player(player: Any, secret: bytes, index: int, subject_player: int) -> dict[str, Any]:
    source = player if isinstance(player, dict) else {}
    own_view = index == subject_player
    hand_source = source.get("hand", []) if own_view else []
    return {
        "name": _text(source.get("name"), f"Player {index + 1}", 120),
        "active": _public_card(source.get("active"), secret, index),
        "bench": [card for raw in source.get("bench", [])[:5] if (card := _public_card(raw, secret, index)) is not None],
        "hand": [card for raw in hand_source[:60] if (card := _public_card(raw, secret, index)) is not None],
        "handCount": _integer(source.get("handCount", len(source.get("hand", [])) if isinstance(source.get("hand"), list) else 0)),
        "deckCount": _integer(source.get("deckCount")),
        "prizeCount": _integer(source.get("prizeCount")),
        "discard": [card for raw in source.get("discard", [])[:60] if (card := _public_card(raw, secret, index)) is not None],
        "supporterPlayed": bool(source.get("supporterPlayed", False)),
        "retreated": bool(source.get("retreated", False)),
    }


def _public_decision(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in _PUBLIC_DECISION_KEYS:
        if key not in value:
            continue
        raw = value[key]
        if key == "actor":
            result[key] = 0 if _integer(raw) == 0 else 1
        elif key in {"confidence", "elapsedMs"}:
            result[key] = _number_or_none(raw)
        elif key == "warnings":
            result[key] = [_text(item, limit=160) for item in raw if isinstance(item, (str, int))][:8] if isinstance(raw, list) else []
        else:
            result[key] = _text(raw, "未記録", 240)
    if "actor" not in result or "chosen" not in result:
        return None
    result.setdefault("goal", "未記録")
    result.setdefault("confidence", None)
    result.setdefault("elapsedMs", None)
    result.setdefault("warnings", [])
    result["candidates"] = []
    return result


def public_battle_frame(frame: Any, secret: bytes, subject_player: int = 0) -> dict[str, Any]:
    source = frame if isinstance(frame, dict) else {}
    players = source.get("players") if isinstance(source.get("players"), (list, tuple)) else []
    padded = list(players[:2]) + [{}] * max(0, 2 - len(players))
    events = []
    for raw in source.get("events", []) if isinstance(source.get("events"), list) else []:
        if not isinstance(raw, dict):
            continue
        actor = raw.get("actor")
        events.append({
            "type": _text(raw.get("type"), "event", 64),
            "actor": actor if actor in (0, 1) else None,
            "text": _text(raw.get("text"), "対戦が進行しました", 240),
            "cardKey": None,
        })
    acting = _integer(source.get("actingPlayer"))
    return {
        "frameId": _integer(source.get("frameId")),
        "turn": _integer(source.get("turn")),
        "actionCount": _integer(source.get("actionCount")),
        "actingPlayer": 0 if acting == 0 else 1,
        "phase": _text(source.get("phase"), "unknown", 64),
        "players": [_public_player(padded[0], secret, 0, subject_player), _public_player(padded[1], secret, 1, subject_player)],
        "stadium": _public_card(source.get("stadium"), secret, _integer(source.get("stadium", {}).get("playerIndex")) if isinstance(source.get("stadium"), dict) else 0),
        "events": events[-100:],
        "decision": _public_decision(source.get("decision")),
        "result": _text(source.get("result"), limit=160) if source.get("result") is not None else None,
    }


def public_error(_error: BaseException | str) -> dict[str, str]:
    return {"type": "error", "code": "ACTION_UNAVAILABLE", "detail": "この操作は実行できませんでした。対戦状態を確認してください。"}

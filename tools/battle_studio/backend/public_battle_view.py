from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from card_catalog import get_catalog


PUBLIC_PROTOCOL_VERSION = "1.0"
_SENSITIVE_MARKERS = (
    "serial", "optionindex", "arrayindex", "select.type", "mincount", "maxcount",
    "context=", "area=", "battleptr", "libcg", "traceback", 'file "',
)
_SAFE_EVENT_TYPES = {
    "attack", "attach", "bench", "damage", "discard", "draw", "evolve", "heal",
    "knockout", "log", "move", "play", "prize", "retreat", "stadium", "status",
    "supporter", "switch", "trainer", "turn",
}


def _seq(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value if value is not None else fallback).replace("\r", " ").replace("\n", " ").split())
    lowered = text.lower()
    if any(marker in lowered for marker in _SENSITIVE_MARKERS):
        return fallback or "対戦状態が更新されました"
    return text[:320]


class PublicBattleView:
    """Convert an internal official-engine frame into a browser-safe player view."""

    def __init__(self, session_nonce: str, subject_player: int = 0) -> None:
        self.subject_player = subject_player if subject_player in (0, 1) else 0
        self._secret = hashlib.sha256(session_nonce.encode("utf-8")).digest()
        self._public_card_ids: dict[int, int] = {}
        self._catalog_entries: dict[int, dict[str, Any]] = {}
        try:
            cards, _sources = get_catalog()
        except (FileNotFoundError, OSError, ValueError):
            cards = []
        self._catalog = {
            _integer(card.get("id")): dict(card)
            for card in cards
            if isinstance(card, Mapping) and _integer(card.get("id")) > 0
        }

    def _opaque_int(self, namespace: str, *parts: Any) -> int:
        digest = hashlib.blake2s(key=self._secret, digest_size=4)
        digest.update(namespace.encode("utf-8"))
        for part in parts:
            digest.update(b"\0")
            digest.update(str(part).encode("utf-8", errors="replace"))
        value = int.from_bytes(digest.digest(), "big") & 0x7FFFFFFF
        return value or 1

    def _public_card_id(self, actual_card_id: int, fallback_name: str = "") -> int:
        if actual_card_id not in self._public_card_ids:
            self._public_card_ids[actual_card_id] = self._opaque_int("card", actual_card_id)
        public_id = self._public_card_ids[actual_card_id]
        if public_id not in self._catalog_entries:
            metadata = self._catalog.get(actual_card_id, {})
            self._catalog_entries[public_id] = {
                "id": public_id,
                "name": _safe_text(metadata.get("name"), fallback_name or "Unknown card"),
                "number": _safe_text(metadata.get("number")),
                "expansion": _safe_text(metadata.get("expansion")),
                "sourceLink": _safe_text(metadata.get("sourceLink")),
            }
        return public_id

    def _card(self, raw: Any, player: int) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        actual_card_id = _integer(raw.get("cardId"))
        name = _safe_text(raw.get("name"), "Unknown card")
        public_card_id = self._public_card_id(actual_card_id, name)
        actual_serial = _integer(raw.get("serial"))
        public_serial = self._opaque_int(
            "instance",
            player,
            actual_serial,
            actual_card_id,
            raw.get("zone"),
            raw.get("slot"),
        )
        return {
            "playerIndex": player,
            "serial": public_serial,
            "cardId": public_card_id,
            "name": name,
            "zone": str(raw.get("zone", "unknown")) if raw.get("zone") in {"active", "bench", "hand", "deck", "discard", "prize", "looking", "unknown"} else "unknown",
            "slot": _integer(raw.get("slot")) if isinstance(raw.get("slot"), int) and raw.get("slot") >= 0 else None,
            "hp": _integer(raw.get("hp")) if isinstance(raw.get("hp"), int) and raw.get("hp") >= 0 else None,
            "maxHp": _integer(raw.get("maxHp")) if isinstance(raw.get("maxHp"), int) and raw.get("maxHp") >= 0 else None,
            "damage": max(0, _integer(raw.get("damage"))),
            "energies": [_safe_text(item, "?") for item in _seq(raw.get("energies"))][:16],
            "tools": [_safe_text(item, "?") for item in _seq(raw.get("tools"))][:8],
            "status": [_safe_text(item, "?") for item in _seq(raw.get("status"))][:8],
            "evolution": [
                self._public_card_id(_integer(item))
                for item in _seq(raw.get("evolution"))
                if _integer(item) > 0
            ][:8],
            "imageUrl": None,
        }

    def _player(self, raw: Any, player: int) -> dict[str, Any]:
        value = raw if isinstance(raw, Mapping) else {}
        own_hand = player == self.subject_player
        hand = [card for item in _seq(value.get("hand")) if (card := self._card(item, player)) is not None] if own_hand else []
        return {
            "name": _safe_text(value.get("name"), f"Player {player + 1}"),
            "active": self._card(value.get("active"), player),
            "bench": [card for item in _seq(value.get("bench")) if (card := self._card(item, player)) is not None][:5],
            "hand": hand,
            "handCount": max(0, _integer(value.get("handCount"), len(hand))),
            "deckCount": max(0, _integer(value.get("deckCount"))),
            "prizeCount": max(0, _integer(value.get("prizeCount"))),
            "discard": [card for item in _seq(value.get("discard")) if (card := self._card(item, player)) is not None],
            "supporterPlayed": bool(value.get("supporterPlayed", False)),
            "retreated": bool(value.get("retreated", False)),
        }

    def _event(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        event_type = str(raw.get("type", "log")).lower()
        public_type = event_type if event_type in _SAFE_EVENT_TYPES else "log"
        actor = raw.get("actor")
        actor_value = int(actor) if actor in (0, 1) else None
        if event_type == "agent_error":
            text = "対戦AIがこの行動を完了できませんでした"
        else:
            text = _safe_text(raw.get("text"), "対戦状態が更新されました")
        return {"type": public_type, "actor": actor_value, "text": text, "cardKey": None}

    def _candidate(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        return {
            "label": _safe_text(raw.get("label"), "候補"),
            "score": float(_number(raw.get("score"), 0.0) or 0.0),
            "selected": bool(raw.get("selected", False)),
            "reason": _safe_text(raw.get("reason")) if raw.get("reason") is not None else None,
            "kind": _safe_text(raw.get("kind")) if raw.get("kind") is not None else None,
        }

    def _search_tree(self, raw: Any, path: str = "root") -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        status = str(raw.get("status", "available"))
        if status not in {"root", "available", "expanded", "selected", "pruned"}:
            status = "available"
        return {
            "id": f"node-{self._opaque_int('search-node', path)}",
            "label": _safe_text(raw.get("label"), "候補"),
            "status": status,
            "ev": _number(raw.get("ev")),
            "visits": max(0, _integer(raw.get("visits"))) if raw.get("visits") is not None else None,
            "mean": _number(raw.get("mean")),
            "worst": _number(raw.get("worst")),
            "best": _number(raw.get("best")),
            "reason": _safe_text(raw.get("reason")) if raw.get("reason") is not None else None,
            "children": [
                node
                for index, item in enumerate(_seq(raw.get("children")))
                if (node := self._search_tree(item, f"{path}/{index}")) is not None
            ],
        }

    def _decision(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping) or raw.get("actor") not in (0, 1):
            return None
        candidates = [item for value in _seq(raw.get("candidates")) if (item := self._candidate(value)) is not None]
        alternatives = [item for value in _seq(raw.get("alternatives")) if (item := self._candidate(value)) is not None]
        chosen = _safe_text(raw.get("chosen"))
        if not chosen or re.fullmatch(r"\s*\[[0-9,\s-]*\]\s*", chosen):
            selected = next((item["label"] for item in candidates if item["selected"]), None)
            chosen = selected or "行動を選択"
        decision: dict[str, Any] = {
            "actor": int(raw["actor"]),
            "goal": _safe_text(raw.get("goal"), "対戦を進める"),
            "chosen": chosen,
            "confidence": _number(raw.get("confidence")),
            "expectedWinRate": _number(raw.get("expectedWinRate")),
            "elapsedMs": max(0.0, _number(raw.get("elapsedMs"), 0.0) or 0.0),
            "candidates": candidates,
            "warnings": [_safe_text(item) for item in _seq(raw.get("warnings"))],
            "alternatives": alternatives,
            "boardDiff": [_safe_text(item) for item in _seq(raw.get("boardDiff"))],
        }
        tree = self._search_tree(raw.get("searchTree"))
        if tree is not None:
            decision["searchTree"] = tree
        rejected = []
        for value in _seq(raw.get("rejectedBranches")):
            if not isinstance(value, Mapping):
                continue
            rejected.append({
                "label": _safe_text(value.get("label"), "候補"),
                "reason": _safe_text(value.get("reason"), "理由未提供"),
                "evidence": [_safe_text(item) for item in _seq(value.get("evidence"))],
                "metrics": {
                    _safe_text(key): item
                    for key, item in dict(value.get("metrics", {})).items()
                    if isinstance(item, (str, int, float)) and not isinstance(item, bool)
                } if isinstance(value.get("metrics"), Mapping) else {},
                "killedBy": [_safe_text(item) for item in _seq(value.get("killedBy"))],
            })
        if rejected:
            decision["rejectedBranches"] = rejected
        return decision

    def render(self, frame: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        players = _seq(frame.get("players"))
        if len(players) != 2:
            raise ValueError("public battle view requires exactly two players")
        public_frame = {
            "frameId": max(0, _integer(frame.get("frameId"))),
            "turn": max(0, _integer(frame.get("turn"))),
            "actionCount": max(0, _integer(frame.get("actionCount"))),
            "actingPlayer": _integer(frame.get("actingPlayer")) if frame.get("actingPlayer") in (0, 1) else 0,
            "phase": _safe_text(frame.get("phase"), "unknown"),
            "players": [self._player(players[0], 0), self._player(players[1], 1)],
            "stadium": self._card(frame.get("stadium"), 0),
            "events": [event for item in _seq(frame.get("events")) if (event := self._event(item)) is not None],
            "decision": self._decision(frame.get("decision")),
            "result": _safe_text(frame.get("result")) if frame.get("result") is not None else None,
        }
        return public_frame, sorted(self._catalog_entries.values(), key=lambda item: int(item["id"]))

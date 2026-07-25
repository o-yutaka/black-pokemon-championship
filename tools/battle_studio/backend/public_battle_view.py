from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from card_catalog import get_catalog


PUBLIC_PROTOCOL_VERSION = "1.1"
_PUBLIC_ZONES = {"active", "bench", "hand", "deck", "discard", "prize", "looking", "unknown"}
_PUBLIC_PHASES = {"setup", "main", "attack", "between_turns", "game_over", "unknown"}
_SAFE_EVENT_TYPES = {
    "attack", "attach", "bench", "damage", "discard", "draw", "evolve", "heal",
    "knockout", "log", "move", "play", "prize", "retreat", "stadium", "status",
    "supporter", "switch", "trainer", "turn",
}
_SAFE_KINDS = {"attack", "ability", "attach", "evolve", "retreat", "switch", "trainer", "supporter", "pass", "other"}
_SAFE_METRICS = {"ev", "visits", "mean", "worst", "best", "delta", "score", "probability", "confidence", "winrate", "elapsedms"}
_ALLOWED_URL_HOSTS = (
    "pokemontcg.io", "pokemon.com", "pokemon-card.com", "limitlesstcg.com",
    "kaggleusercontent.com", "githubusercontent.com",
)
_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/)(?:[^\s\]\[{}]+[\\/])+[^\s\]\[{}]*")
_INTERNAL_RE = re.compile(
    r"\b(?:select(?:ion)?(?:\.type)?|serial|option(?:index)?|arrayindex|area|context|searchid|battleptr|libcg|observation|truthledger|hiddenbelief|selectedaction)\b",
    re.IGNORECASE,
)
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
_HEX_RE = re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE)
_JSONISH_RE = re.compile(r"[{}]|\[[^\]]*[:{},][^\]]*\]")


def _seq(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    parsed = float(value)
    return parsed if math.isfinite(parsed) else default


def _integer(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, fallback: str = "", limit: int = 240) -> str:
    text = " ".join(str(value if value is not None else fallback).replace("\r", " ").replace("\n", " ").split())
    if not text:
        return fallback
    if _PATH_RE.search(text) or _INTERNAL_RE.search(text) or _LONG_NUMBER_RE.search(text) or _HEX_RE.search(text) or _JSONISH_RE.search(text):
        return fallback or "対戦状態が更新されました"
    return text[:limit]


def _safe_url(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(host == allowed or host.endswith("." + allowed) for allowed in _ALLOWED_URL_HOSTS):
        return ""
    return value[:500]


class PublicBattleView:
    """Strict player-safe projection for every official runtime transport."""

    def __init__(self, session_nonce: str, subject_player: int = 0) -> None:
        self.subject_player = subject_player if subject_player in (0, 1) else 0
        self._secret = hashlib.sha256(session_nonce.encode("utf-8")).digest()
        self._public_card_ids: dict[tuple[int, str], int] = {}
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
        key = (actual_card_id, fallback_name if actual_card_id <= 0 else "")
        if key not in self._public_card_ids:
  self._public_card_ids[key] = self._opaque_int("card", *key)
        public_id = self._public_card_ids[key]
        if public_id not in self._catalog_entries:
  metadata = self._catalog.get(actual_card_id, {})
  self._catalog_entries[public_id] = {
      "id": public_id,
      "name": _safe_text(metadata.get("name"), fallback_name or "Unknown card", 120),
      "number": _safe_text(metadata.get("number"), "", 40),
      "expansion": _safe_text(metadata.get("expansion"), "", 100),
      "sourceLink": _safe_url(metadata.get("sourceLink")),
  }
        return public_id

    def _attachment_label(self, raw: Any, fallback: str) -> str:
        if isinstance(raw, Mapping):
  named = _safe_text(raw.get("name"), "", 100)
  if named:
      return named
  raw = raw.get("cardId", raw.get("id"))
        card_id = _integer(raw, -1)
        if card_id > 0:
  name = _safe_text(self._catalog.get(card_id, {}).get("name"), "", 100)
  return name or fallback
        text = _safe_text(raw, "", 100)
        if text and not text.isdigit():
  return text
        return fallback

    def _card(self, raw: Any, player: int) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
  return None
        actual_card_id = _integer(raw.get("cardId"))
        name = _safe_text(raw.get("name"), "Unknown card", 120)
        public_card_id = self._public_card_id(actual_card_id, name)
        actual_serial = _integer(raw.get("serial"))
        instance_seed: Any = actual_serial if actual_serial > 0 else (actual_card_id, name)
        public_serial = self._opaque_int("instance", player, instance_seed)
        zone = str(raw.get("zone", "unknown"))
        return {
  "playerIndex": player,
  "serial": public_serial,
  "cardId": public_card_id,
  "name": name,
  "zone": zone if zone in _PUBLIC_ZONES else "unknown",
  "slot": _integer(raw.get("slot")) if isinstance(raw.get("slot"), int) and raw.get("slot") >= 0 else None,
  "hp": _integer(raw.get("hp")) if isinstance(raw.get("hp"), int) and raw.get("hp") >= 0 else None,
  "maxHp": _integer(raw.get("maxHp")) if isinstance(raw.get("maxHp"), int) and raw.get("maxHp") >= 0 else None,
  "damage": max(0, _integer(raw.get("damage"))),
  "energies": [self._attachment_label(item, "エネルギー") for item in _seq(raw.get("energies"))][:16],
  "tools": [self._attachment_label(item, "ポケモンのどうぐ") for item in _seq(raw.get("tools"))][:8],
  "status": [_safe_text(item, "状態異常", 48) for item in _seq(raw.get("status"))][:8],
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
  "name": "自分" if own_hand else "相手",
  "active": self._card(value.get("active"), player),
  "bench": [card for item in _seq(value.get("bench")) if (card := self._card(item, player)) is not None][:5],
  "hand": hand,
  "handCount": max(0, _integer(value.get("handCount"), len(hand))),
  "deckCount": max(0, _integer(value.get("deckCount"))),
  "prizeCount": max(0, _integer(value.get("prizeCount"))),
  "discard": [card for item in _seq(value.get("discard")) if (card := self._card(item, player)) is not None][:60],
  "supporterPlayed": bool(value.get("supporterPlayed", False)),
  "retreated": bool(value.get("retreated", False)),
        }

    def _event(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
  return None
        event_type = str(raw.get("type", "log")).lower()
        actor = raw.get("actor")
        text = "対戦AIがこの行動を完了できませんでした" if event_type == "agent_error" else _safe_text(raw.get("text"), "対戦状態が更新されました")
        return {
  "type": event_type if event_type in _SAFE_EVENT_TYPES else "log",
  "actor": int(actor) if actor in (0, 1) else None,
  "text": text,
  "cardKey": None,
        }

    def _candidate(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
  return None
        raw_kind = str(raw.get("kind", "")).lower()
        return {
  "label": _safe_text(raw.get("label"), "候補", 120),
  "score": float(_number(raw.get("score"), 0.0) or 0.0),
  "selected": bool(raw.get("selected", False)),
  "reason": _safe_text(raw.get("reason"), "理由未提供") if raw.get("reason") is not None else None,
  "kind": raw_kind if raw_kind in _SAFE_KINDS else None,
        }

    def _search_tree(self, raw: Any, path: str = "root") -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
  return None
        status = str(raw.get("status", "available"))
        if status not in {"root", "available", "expanded", "selected", "pruned"}:
  status = "available"
        return {
  "id": f"node-{self._opaque_int('search-node', path)}",
  "label": _safe_text(raw.get("label"), "候補", 120),
  "status": status,
  "ev": _number(raw.get("ev")),
  "visits": max(0, _integer(raw.get("visits"))) if raw.get("visits") is not None else None,
  "mean": _number(raw.get("mean")),
  "worst": _number(raw.get("worst")),
  "best": _number(raw.get("best")),
  "reason": _safe_text(raw.get("reason"), "理由未提供") if raw.get("reason") is not None else None,
  "children": [
      node
      for index, item in enumerate(_seq(raw.get("children")))
      if (node := self._search_tree(item, f"{path}/{index}")) is not None
  ][:64],
        }

    def _decision(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping) or raw.get("actor") not in (0, 1):
  return None
        candidates = [item for value in _seq(raw.get("candidates")) if (item := self._candidate(value)) is not None][:32]
        alternatives = [item for value in _seq(raw.get("alternatives")) if (item := self._candidate(value)) is not None][:32]
        raw_chosen = str(raw.get("chosen", ""))
        if not raw_chosen or re.fullmatch(r"\s*\[[0-9,\s-]*\]\s*", raw_chosen):
  chosen = next((item["label"] for item in candidates if item["selected"]), "行動を選択")
        else:
  chosen = _safe_text(raw_chosen, "行動を選択", 120)
        decision: dict[str, Any] = {
  "actor": int(raw["actor"]),
  "goal": _safe_text(raw.get("goal"), "対戦を進める"),
  "chosen": chosen,
  "confidence": _number(raw.get("confidence")),
  "expectedWinRate": _number(raw.get("expectedWinRate")),
  "elapsedMs": max(0.0, _number(raw.get("elapsedMs"), 0.0) or 0.0),
  "candidates": candidates,
  "warnings": [_safe_text(item, "注意事項", 160) for item in _seq(raw.get("warnings"))][:16],
  "alternatives": alternatives,
  "boardDiff": [_safe_text(item, "盤面が変化しました", 160) for item in _seq(raw.get("boardDiff"))][:16],
        }
        tree = self._search_tree(raw.get("searchTree"))
        if tree is not None:
  decision["searchTree"] = tree
        rejected = []
        for value in _seq(raw.get("rejectedBranches"))[:32]:
  if not isinstance(value, Mapping):
      continue
  metrics: dict[str, float] = {}
  if isinstance(value.get("metrics"), Mapping):
      for key, item in value["metrics"].items():
          canonical = str(key).lower().replace("_", "")
          number = _number(item)
          if canonical in _SAFE_METRICS and number is not None:
              metrics[canonical] = number
  rejected.append({
      "label": _safe_text(value.get("label"), "候補", 120),
      "reason": _safe_text(value.get("reason"), "理由未提供"),
      "evidence": [_safe_text(item, "公開可能な証拠なし", 160) for item in _seq(value.get("evidence"))][:16],
      "metrics": metrics,
      "killedBy": [_safe_text(item, "安全条件", 120) for item in _seq(value.get("killedBy"))][:16],
  })
        if rejected:
  decision["rejectedBranches"] = rejected
        return decision

    def render(self, frame: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        players = _seq(frame.get("players"))
        if len(players) != 2:
  raise ValueError("public battle view requires exactly two players")
        phase = str(frame.get("phase", "unknown")).lower()
        public_frame = {
  "frameId": max(0, _integer(frame.get("frameId"))),
  "turn": max(0, _integer(frame.get("turn"))),
  "actionCount": max(0, _integer(frame.get("actionCount"))),
  "actingPlayer": _integer(frame.get("actingPlayer")) if frame.get("actingPlayer") in (0, 1) else 0,
  "phase": phase if phase in _PUBLIC_PHASES else "unknown",
  "players": [self._player(players[0], 0), self._player(players[1], 1)],
  "stadium": self._card(frame.get("stadium"), 0),
  "events": [event for item in _seq(frame.get("events"))[-100:] if (event := self._event(item)) is not None],
  "decision": self._decision(frame.get("decision")),
  "result": _safe_text(frame.get("result"), "対戦終了", 160) if frame.get("result") is not None else None,
        }
        return public_frame, sorted(self._catalog_entries.values(), key=lambda item: int(item["id"]))

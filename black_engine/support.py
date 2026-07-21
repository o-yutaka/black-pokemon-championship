from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_DISCARD, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 11, 12, 13, 14
AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH, AREA_PRIZE = 2, 3, 4, 5, 6


def read_deck(path: str | Path) -> list[int]:
    values: list[int] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            raw = str(row[0]).strip()
            if not raw.isdigit():
                raise ValueError(f"invalid deck value: {raw!r}")
            values.append(int(raw))
    return values


def fingerprint(ids: Iterable[int]) -> str:
    counts = Counter(int(value) for value in ids)
    return ",".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def validate_deck(ids: Iterable[int], ace_spec_ids: set[int]) -> dict:
    cards = [int(value) for value in ids]
    counts = Counter(cards)
    violations: list[str] = []
    if len(cards) != 60:
        violations.append(f"deck_size={len(cards)} expected=60")
    for cid, count in sorted(counts.items()):
        if count > 4 and cid not in set(range(1, 10)):
            violations.append(f"copy_limit card_id={cid} count={count}")
    ace_count = sum(counts[value] for value in ace_spec_ids)
    if ace_count != 1:
        violations.append(f"ace_spec_count={ace_count} expected=1")
    return {"ok": not violations, "total": len(cards), "unique": len(counts), "fingerprint": fingerprint(cards), "ace_spec_count": ace_count, "violations": violations}


def normalize_selection(obs: dict | None, action: Any):
    if not isinstance(obs, dict) or not isinstance(obs.get("select"), dict):
        return action
    select = obs["select"]
    options = select.get("option") if isinstance(select.get("option"), list) else []
    minimum = max(0, int(select.get("minCount", 1) or 0))
    maximum = max(0, int(select.get("maxCount", 1) or 0))
    capacity = min(maximum, len(options))
    if capacity <= 0:
        return []
    raw = action if isinstance(action, (list, tuple)) else [action]
    chosen: list[int] = []
    for item in raw:
        if type(item) is int and 0 <= item < len(options) and item not in chosen:
            chosen.append(item)
            if len(chosen) >= capacity:
                break
    for index in range(len(options)):
        if len(chosen) >= min(minimum, capacity):
            break
        if index not in chosen:
            chosen.append(index)
    return [] if not chosen and minimum == 0 else chosen[:capacity]


def my_index(obs: dict) -> int:
    value = (obs.get("current") or {}).get("yourIndex", 0)
    return value if type(value) is int else 0


def player(obs: dict, index: int) -> dict:
    values = (obs.get("current") or {}).get("players") or []
    return values[index] if 0 <= index < len(values) and isinstance(values[index], dict) else {}


def zone(obs: dict, index: int, name: str) -> list:
    value = player(obs, index).get(name)
    return value if isinstance(value, list) else []


def active(obs: dict, index: int) -> dict:
    values = zone(obs, index, "active")
    return values[0] if values and isinstance(values[0], dict) else {}


def bench(obs: dict, index: int) -> list[dict]:
    return [value for value in zone(obs, index, "bench") if isinstance(value, dict)]


def in_play(obs: dict, index: int) -> list[dict]:
    current = active(obs, index)
    return ([current] if current else []) + bench(obs, index)


def zone_cards(current: dict | None, player_index: int, area: int | None) -> list:
    if not isinstance(current, dict):
        return []
    players = current.get("players") or []
    p = players[player_index] if 0 <= player_index < len(players) else {}
    if not isinstance(p, dict):
        return []
    key = {AREA_HAND: "hand", AREA_DISCARD: "discard", AREA_ACTIVE: "active", AREA_BENCH: "bench", AREA_PRIZE: "prize"}.get(area)
    value = p.get(key) if key else None
    return value if isinstance(value, list) else []


def card_id(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            raw = value.get(key)
            if type(raw) is int:
                return raw
    return value if type(value) is int else -1


def option_card_id(option: dict, current: dict | None = None, default_player_index: int = 0) -> int:
    if not isinstance(option, dict):
        return -1
    for key in ("card", "cardId", "id"):
        resolved = card_id(option.get(key))
        if resolved >= 0:
            return resolved
    area = option.get("area")
    if area is None and option.get("type") == T_PLAY:
        area = AREA_HAND
    index = option.get("index")
    player_index = option.get("playerIndex", default_player_index)
    if type(player_index) is not int:
        player_index = default_player_index
    if isinstance(area, int) and isinstance(index, int):
        cards = zone_cards(current, player_index, area)
        if 0 <= index < len(cards) and isinstance(cards[index], dict):
            return card_id(cards[index])
    return -1


def option_target_id(option: dict, current: dict | None = None, default_player_index: int = 0) -> int:
    if not isinstance(option, dict):
        return -1
    for key in ("target", "pokemon", "to", "selectPokemon"):
        resolved = card_id(option.get(key))
        if resolved >= 0:
            return resolved
    area, index = option.get("inPlayArea"), option.get("inPlayIndex")
    player_index = option.get("playerIndex", default_player_index)
    if type(player_index) is not int:
        player_index = default_player_index
    if isinstance(area, int) and isinstance(index, int):
        cards = zone_cards(current, player_index, area)
        if 0 <= index < len(cards) and isinstance(cards[index], dict):
            return card_id(cards[index])
    return -1


def option_attack_id(option: dict) -> int:
    value = option.get("attackId")
    return value if type(value) is int else -1


def energy_count(pokemon: dict) -> int:
    for key in ("energyCards", "energies", "energy"):
        value = pokemon.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def max_hp(pokemon: dict) -> int:
    for key in ("maxHp", "maxHP", "HP"):
        value = pokemon.get(key)
        if type(value) in (int, float):
            return max(0, int(value))
    return 0


def remaining_hp(pokemon: dict) -> int:
    value = pokemon.get("hp")
    if type(value) in (int, float):
        return max(0, int(value))
    return max_hp(pokemon)


def damage_points(pokemon: dict) -> int:
    return max(0, max_hp(pokemon) - remaining_hp(pokemon))


class ScoredPolicy(ABC):
    def __init__(self) -> None:
        self.deck: list[int] = []

    def set_deck(self, ids: list[int]) -> None:
        self.deck = [int(value) for value in ids]

    @abstractmethod
    def build_context(self, obs: dict) -> dict: ...

    @abstractmethod
    def score_option(self, option: dict, context: dict) -> float: ...

    def choose_single(self, options: list, context: dict) -> int:
        return max(((self.score_option(value, context) if isinstance(value, dict) else -1e9, index) for index, value in enumerate(options)), default=(0, 0))[1]

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        scored = sorted(((self.score_option(value, context) if isinstance(value, dict) else -1e9, index) for index, value in enumerate(options)), reverse=True)
        count = max(minimum, min(maximum, len(scored))) if maximum > 0 else 0
        return [index for _, index in scored[:count]]

    def agent(self, obs: dict | None, configuration=None):
        if obs is None or not isinstance(obs, dict) or obs.get("select") is None:
            return list(self.deck)
        select = obs.get("select") or {}
        options = select.get("option") if isinstance(select.get("option"), list) else []
        if not options:
            return []
        context = self.build_context(obs)
        minimum = max(0, int(select.get("minCount", 1) or 0))
        maximum = max(0, int(select.get("maxCount", 1) or 0))
        raw = self.choose_single(options, context) if minimum == maximum == 1 else self.choose_multi(options, context, minimum, maximum)
        return normalize_selection(obs, raw)

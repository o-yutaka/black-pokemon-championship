from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH, AREA_PRIZE = 1, 2, 3, 4, 5, 6
T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
CTX_SETUP_ACTIVE, CTX_SETUP_BENCH = 1, 2


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _card_id(value: Any) -> int:
    if type(value) is int:
        return value
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            raw = value.get(key)
            if type(raw) is int:
                return raw
    return -1


def _actor(obs: dict) -> int:
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    value = current.get("yourIndex", 0)
    return value if value in (0, 1) else 0


def _player(obs: dict, index: int) -> dict:
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    players = current.get("players") if isinstance(current.get("players"), list) else []
    return players[index] if 0 <= index < len(players) and isinstance(players[index], dict) else {}


def _zone(obs: dict, player_index: int, area: int | None) -> list:
    key = {
        AREA_DECK: "deck",
        AREA_HAND: "hand",
        AREA_DISCARD: "discard",
        AREA_ACTIVE: "active",
        AREA_BENCH: "bench",
        AREA_PRIZE: "prize",
    }.get(area)
    value = _player(obs, player_index).get(key) if key else None
    return _list(value)


def _resolve_option_card(obs: dict, option: dict, actor: int) -> int:
    for key in ("card", "cardId", "id"):
        value = _card_id(option.get(key))
        if value >= 0:
            return value
    area = option.get("area")
    if area is None and option.get("type") == T_PLAY:
        area = AREA_HAND
    index = option.get("index")
    player_index = option.get("playerIndex", actor)
    if type(player_index) is not int:
        player_index = actor
    values = _zone(obs, player_index, area)
    if type(index) is int and 0 <= index < len(values):
        return _card_id(values[index])
    return -1


def _resolve_target(obs: dict, option: dict, actor: int) -> tuple[int, int, dict | None]:
    player_index = option.get("playerIndex", actor)
    if type(player_index) is not int or player_index not in (0, 1):
        player_index = actor
    area = option.get("inPlayArea")
    index = option.get("inPlayIndex")
    values = _zone(obs, player_index, area)
    if type(index) is int and 0 <= index < len(values) and isinstance(values[index], dict):
        return player_index, _card_id(values[index]), values[index]
    return player_index, -1, None


def _remaining_hp(value: dict | None) -> int:
    if not isinstance(value, dict):
        return 0
    hp = value.get("hp")
    if type(hp) in (int, float):
        return max(0, int(hp))
    max_hp = value.get("maxHp")
    return max(0, int(max_hp)) if type(max_hp) in (int, float) else 0


def _energy_count(value: dict | None) -> int:
    if not isinstance(value, dict):
        return 0
    cards = value.get("energyCards")
    if isinstance(cards, list):
        return len(cards)
    energies = value.get("energies")
    return len(energies) if isinstance(energies, list) else 0


def _rank(order: list[int], card_id: int, default: int = -100) -> int:
    try:
        return (len(order) - order.index(card_id)) * 100
    except ValueError:
        return default


class ReplayGroundedPolicy:
    """Deck-specific official-option policy reconstructed from official replays.

    This is not the original competitor source. Its evidence identity is always
    REPLAY_GROUNDED_RECONSTRUCTION. Every action remains an index from the
    official legal option list.
    """

    def __init__(self, deck: list[int], profile: dict):
        self.deck = list(deck)
        self.profile = dict(profile)

    def _profile_order(self, key: str) -> list[int]:
        return [int(value) for value in self.profile.get(key, [])]

    def _score(self, obs: dict, option: dict, index: int) -> float:
        actor = _actor(obs)
        select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
        context = int(select.get("context", -1) or -1)
        kind = option.get("type") if type(option.get("type")) is int else -1
        cid = _resolve_option_card(obs, option, actor)
        target_player, target_id, target = _resolve_target(obs, option, actor)
        setup_active = self._profile_order("setup_active_order")
        setup_bench = self._profile_order("setup_bench_order")
        evolve = self._profile_order("evolution_order")
        energy_targets = self._profile_order("energy_target_order")
        switch = self._profile_order("switch_order")
        search = self._profile_order("search_order")
        play = self._profile_order("play_order")
        opponent_targets = self._profile_order("opponent_target_order")

        if context == CTX_SETUP_ACTIVE:
            return 10000.0 + _rank(setup_active, cid) - index * 0.001
        if context == CTX_SETUP_BENCH:
            return 9000.0 + _rank(setup_bench, cid) - index * 0.001

        if kind == T_ATTACK:
            attack_id = option.get("attackId")
            if type(attack_id) is not int and isinstance(option.get("attack"), dict):
                attack_id = option["attack"].get("attackId", option["attack"].get("id", -1))
            priority = float(self.profile.get("attack_priority", {}).get(str(attack_id), 100.0))
            damage = int(self.profile.get("attack_damage", {}).get(str(attack_id), 0))
            opponent_active = (_player(obs, 1 - actor).get("active") or [None])[0]
            if damage >= _remaining_hp(opponent_active) > 0:
                priority += 10000.0
            turn = int((obs.get("current") or {}).get("turn", 0) or 0)
            if cid == 235 and turn <= 4:
                priority += 800.0
            return 20000.0 + priority - index * 0.001

        if kind == T_EVOLVE:
            return 15000.0 + _rank(evolve, cid) + _rank(evolve, target_id, 0) - index * 0.001

        if kind == T_ENERGY:
            score = 13000.0 + _rank(energy_targets, target_id)
            if target is not None:
                score -= 80.0 * _energy_count(target)
            return score - index * 0.001

        if kind == T_ABILITY:
            return 12500.0 + _rank(evolve + switch, cid, 0) - index * 0.001

        if kind == T_PLAY:
            score = 11000.0 + _rank(play, cid)
            active = (_player(obs, actor).get("active") or [None])[0]
            if cid == 1229 and isinstance(active, dict):
                max_hp = active.get("maxHp", active.get("hp", 0))
                if type(max_hp) in (int, float) and _remaining_hp(active) < int(max_hp):
                    score += 4000.0
                else:
                    score -= 5000.0
            return score - index * 0.001

        if kind == T_RETREAT or context in (3, 4):
            score = 10000.0 + _rank(switch, target_id)
            if target is not None:
                score += 100.0 * _energy_count(target)
            return score - index * 0.001

        if kind == T_END:
            return -10000.0 - index * 0.001

        if target_player == 1 - actor and target_id >= 0:
            return 8000.0 + _rank(opponent_targets, target_id) - index * 0.001
        if target_player == actor and target_id >= 0:
            return 7500.0 + _rank(energy_targets + switch + evolve, target_id) - index * 0.001
        if cid >= 0:
            return 7000.0 + _rank(search + play + evolve, cid) - index * 0.001
        return float(-index)

    def agent(self, obs: dict | None, configuration=None) -> list[int]:
        if not isinstance(obs, dict) or (obs.get("current") is None and obs.get("select") is None):
            return list(self.deck)
        select = obs.get("select") if isinstance(obs.get("select"), dict) else None
        if select is None:
            return []
        options = select.get("option") if isinstance(select.get("option"), list) else []
        minimum = max(0, int(select.get("minCount", 0) or 0))
        maximum_raw = select.get("maxCount", minimum)
        maximum = minimum if maximum_raw is None else max(0, int(maximum_raw))
        if not options:
            return []
        ranked = sorted(
            ((self._score(obs, option if isinstance(option, dict) else {}, index), index) for index, option in enumerate(options)),
            reverse=True,
        )
        if minimum == maximum == 1:
            return [ranked[0][1]]
        count = min(maximum, len(options))
        if minimum == 0:
            positive = [row for row in ranked if row[0] > 0]
            count = min(count, len(positive))
            chosen = positive[:count]
        else:
            count = max(minimum, count)
            chosen = ranked[:count]
        return [index for _, index in chosen]


def read_deck(path: str | Path) -> list[int]:
    values: list[int] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if row and str(row[0]).strip().isdigit():
                values.append(int(str(row[0]).strip()))
    if len(values) != 60:
        raise ValueError(f"deck must contain 60 cards, got {len(values)}")
    return values


def load_policy(root: str | Path) -> ReplayGroundedPolicy:
    root = Path(root)
    deck = read_deck(root / "deck.csv")
    profile = json.loads((root / "profile.json").read_text(encoding="utf-8"))
    return ReplayGroundedPolicy(deck, profile)

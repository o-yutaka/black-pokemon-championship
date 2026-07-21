from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14


def read_deck(path: str | Path) -> list[int]:
    values: list[int] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if row and str(row[0]).strip().isdigit():
                values.append(int(row[0]))
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
    for card_id_, count in sorted(counts.items()):
        if count > 4 and card_id_ not in set(range(1, 10)):
            violations.append(f"copy_limit card_id={card_id_} count={count}")
    ace_count = sum(counts[value] for value in ace_spec_ids)
    if ace_count != 1:
        violations.append(f"ace_spec_count={ace_count} expected=1")
    return {
        "ok": not violations,
        "total": len(cards),
        "unique": len(counts),
        "fingerprint": fingerprint(cards),
        "ace_spec_count": ace_count,
        "violations": violations,
    }


def normalize_selection(obs: dict | None, action: Any):
    if not isinstance(obs, dict) or not isinstance(obs.get("select"), dict):
        return action
    select = obs["select"]
    options = select.get("option") if isinstance(select.get("option"), list) else []
    minimum = max(0, int(select.get("minCount", 1) if select.get("minCount") is not None else 1))
    maximum = max(0, int(select.get("maxCount", 1) if select.get("maxCount") is not None else 1))
    capacity = min(maximum, len(options))
    if capacity <= 0:
        return [] if minimum == 0 else action
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


def card_id(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            raw = value.get(key)
            if type(raw) is int:
                return raw
    return value if type(value) is int else -1


def option_card_id(option: dict) -> int:
    for key in ("card", "cardId", "id"):
        value = option.get(key)
        resolved = card_id(value)
        if resolved >= 0:
            return resolved
    return -1


def option_target_id(option: dict) -> int:
    for key in ("target", "pokemon", "to", "selectPokemon"):
        resolved = card_id(option.get(key))
        if resolved >= 0:
            return resolved
    return -1


def option_label(option: dict) -> str:
    values = [str(option[key]) for key in ("name", "text", "label", "attackName", "moveName") if isinstance(option.get(key), str)]
    attack = option.get("attack")
    if isinstance(attack, dict):
        values.extend(str(attack[key]) for key in ("name", "text") if isinstance(attack.get(key), str))
    return " ".join(values).lower()


def energy_count(pokemon: dict) -> int:
    for key in ("energyCards", "energies", "energy"):
        value = pokemon.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def damage_points(pokemon: dict) -> int:
    for key in ("damage", "damagePoints", "damageAmount"):
        value = pokemon.get(key)
        if type(value) in (int, float):
            return max(0, int(value))
    for key in ("damageCounter", "damageCounters"):
        value = pokemon.get(key)
        if type(value) in (int, float):
            numeric = max(0, int(value))
            return numeric * 10 if numeric < 100 else numeric
        if isinstance(value, list):
            return len(value) * 10
    return 0


def max_hp(pokemon: dict) -> int:
    for key in ("maxHp", "maxHP", "hp", "HP"):
        value = pokemon.get(key)
        if type(value) in (int, float):
            return max(0, int(value))
    return 0


def remaining_hp(pokemon: dict) -> int:
    maximum = max_hp(pokemon)
    return max(0, maximum - damage_points(pokemon)) if maximum else 0


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
        scored = sorted(((self.score_option(value, context) if isinstance(value, dict) else 0, index) for index, value in enumerate(options)), reverse=True)
        return [index for _, index in scored[:max(minimum, min(maximum, len(scored)))]] if maximum > 0 else []

    def agent(self, obs: dict | None, configuration=None):
        if obs is None or not isinstance(obs, dict) or obs.get("select") is None:
            return list(self.deck)
        select = obs.get("select") or {}
        options = select.get("option") if isinstance(select.get("option"), list) else []
        if not options:
            return [] if int(select.get("minCount", 0) or 0) == 0 else list(self.deck)
        context = self.build_context(obs)
        minimum, maximum = max(0, int(select.get("minCount", 1) or 0)), max(0, int(select.get("maxCount", 1) or 0))
        raw = self.choose_single(options, context) if minimum == maximum == 1 else self.choose_multi(options, context, minimum, maximum)
        return normalize_selection(obs, raw)


# Team Rocket Mewtwo / Spidops
TAROUNTULA, SPIDOPS, ARTICUNO, MEWTWO_EX, WOBBUFFET, MURKROW = 400, 401, 414, 431, 432, 463
ROCKET_POKEMON = {TAROUNTULA, SPIDOPS, ARTICUNO, MEWTWO_EX, WOBBUFFET, MURKROW}
BUG_CATCHING_SET, NIGHT_STRETCHER, ENERGY_SEARCH, ROCKET_TRANSCEIVER, POKE_PAD = 1094, 1097, 1119, 1134, 1152
HEROES_CAPE, BRAVE_BANGLE, ARIANA, ARCHER, GIOVANNI, PROTON, LILLIE, ROCKET_FACTORY, TEAM_ROCKET_ENERGY = 1159, 1175, 1216, 1217, 1218, 1220, 1227, 1257, 15


def erasure_ball_damage(discard_count: int) -> int:
    return 160 + 60 * max(0, min(2, int(discard_count)))


def minimum_erasure_discards(target_remaining_hp: int) -> int | None:
    return 0 if target_remaining_hp <= 160 else 1 if target_remaining_hp <= 220 else 2 if target_remaining_hp <= 280 else None


class MewtwoSpidopsPolicy(ScoredPolicy):
    def build_context(self, obs: dict) -> dict:
        me, opponent = my_index(obs), 1 - my_index(obs)
        mine, my_active, opp_active = in_play(obs, me), active(obs, me), active(obs, opponent)
        rocket_count = sum(card_id(value) in ROCKET_POKEMON for value in mine)
        return {
            "active_id": card_id(my_active), "active_energy": energy_count(my_active), "rocket_count": rocket_count,
            "four_rocket": rocket_count >= 4, "reservoir_energy": sum(energy_count(value) for value in bench(obs, me)),
            "opp_remaining_hp": remaining_hp(opp_active),
            "damaged_rocket": max((damage_points(value) for value in bench(obs, me) if card_id(value) in ROCKET_POKEMON), default=0),
            "spidops_in_play": any(card_id(value) == SPIDOPS for value in mine),
            "mewtwo_in_play": any(card_id(value) == MEWTWO_EX for value in mine),
        }

    def score_option(self, option: dict, ctx: dict) -> float:
        kind, card, target, label = option.get("type"), option_card_id(option), option_target_id(option), option_label(option)
        if kind == T_ATTACK:
            if ctx["active_id"] == MEWTWO_EX:
                if not ctx["four_rocket"]: return -10000
                needed = minimum_erasure_discards(ctx["opp_remaining_hp"])
                return (980 if ctx["reservoir_energy"] >= 2 else 900) if needed is None else 1300 + (2 - needed) * 20
            if ctx["active_id"] == WOBBUFFET:
                return 1260 if ctx["opp_remaining_hp"] and ctx["damaged_rocket"] >= ctx["opp_remaining_hp"] else 760 + min(300, ctx["damaged_rocket"])
            if ctx["active_id"] == SPIDOPS: return 780 + 30 * ctx["rocket_count"]
            if ctx["active_id"] == ARTICUNO: return 850
            if ctx["active_id"] == MURKROW and "deceit" in label: return 720 if ctx["rocket_count"] < 4 else 380
            return 100
        if kind == T_EVOLVE: return 1020 if card == SPIDOPS else 300
        if kind == T_ABILITY: return 1080 if ctx["spidops_in_play"] or card == SPIDOPS or "charging up" in label else 500
        if kind == T_ENERGY:
            if target == MEWTWO_EX: return 1100 if card == TEAM_ROCKET_ENERGY else (990 if ctx["active_energy"] < 3 else 620)
            if target == SPIDOPS: return 760 if ctx["reservoir_energy"] < 2 else 420
            if target == ARTICUNO and card == TEAM_ROCKET_ENERGY: return 700
            return 500
        if kind == T_PLAY:
            if card == PROTON: return 1100 if ctx["rocket_count"] < 4 else 180
            if card in {BUG_CATCHING_SET, ROCKET_TRANSCEIVER, POKE_PAD, MURKROW}: return 980 if ctx["rocket_count"] < 4 else 500
            if card == GIOVANNI: return 1040 if ctx["four_rocket"] and ctx["active_id"] == MEWTWO_EX else 260
            if card in {ARIANA, LILLIE, ROCKET_FACTORY}: return 820
            if card == HEROES_CAPE: return 860 if target == MEWTWO_EX else 550
            if card == BRAVE_BANGLE: return 680 if target in {SPIDOPS, WOBBUFFET, ARTICUNO} else 300
            if card == ARCHER: return 740
            if card == NIGHT_STRETCHER: return 460
            if card == ENERGY_SEARCH: return 650
            if card in ROCKET_POKEMON: return 900 if ctx["rocket_count"] < 4 else 430
            return 350
        if kind == T_RETREAT: return 920 if ctx["active_id"] != MEWTWO_EX and ctx["four_rocket"] and ctx["mewtwo_in_play"] else 120
        return 0

    def choose_multi(self, options: list, context: dict, minimum: int, maximum: int) -> list[int]:
        if context["active_id"] == MEWTWO_EX and minimum == 0 and maximum <= 2:
            needed = minimum_erasure_discards(context["opp_remaining_hp"])
            if needed is None: needed = min(2, len(options)) if context["reservoir_energy"] >= 3 else 0
            return list(range(min(needed, len(options), maximum)))
        return super().choose_multi(options, context, minimum, maximum)


# Cynthia Garchomp / Spiritomb
ROSELIA, ROSERADE, GIBLE, GABITE, GARCHOMP_EX, SPIRITOMB = 341, 342, 379, 380, 381, 387
CYNTHIA_POKEMON = {ROSELIA, ROSERADE, GIBLE, GABITE, GARCHOMP_EX, SPIRITOMB}
UNFAIR_STAMP, POFFIN, NIGHT_STRETCHER, FIGHTING_GONG, POKE_PAD, POWER_WEIGHT, BOSS, XEROSIC, SURFER, HILDA, LILLIE, FOREST = 1080, 1086, 1097, 1142, 1152, 1173, 1182, 1197, 1203, 1225, 1227, 1261


def spiritomb_effective_damage(benched_cynthia_damage_points: int, roserade_count: int) -> int:
    return max(0, int(benched_cynthia_damage_points)) + 30 * max(0, int(roserade_count))


def garchomp_damage(heavy: bool, roserade_count: int) -> int:
    return (260 if heavy else 100) + 30 * max(0, int(roserade_count))


class GarchompSpiritombPolicy(ScoredPolicy):
    def build_context(self, obs: dict) -> dict:
        me, opponent = my_index(obs), 1 - my_index(obs)
        mine, my_bench, my_active, opp_active = in_play(obs, me), bench(obs, me), active(obs, me), active(obs, opponent)
        roses = sum(card_id(value) == ROSERADE for value in mine)
        reservoir = sum(damage_points(value) for value in my_bench if card_id(value) in CYNTHIA_POKEMON)
        return {
            "active_id": card_id(my_active), "active_energy": energy_count(my_active), "roserade_count": roses,
            "reservoir_damage": reservoir, "spiritomb_damage": spiritomb_effective_damage(reservoir, roses),
            "opp_remaining_hp": remaining_hp(opp_active),
            "garchomp_in_play": any(card_id(value) == GARCHOMP_EX for value in mine),
            "spiritomb_in_play": any(card_id(value) == SPIRITOMB for value in mine),
            "gabite_in_play": any(card_id(value) == GABITE for value in mine),
        }

    def score_option(self, option: dict, ctx: dict) -> float:
        kind, card, target, label = option.get("type"), option_card_id(option), option_target_id(option), option_label(option)
        if kind == T_ATTACK:
            if ctx["active_id"] == SPIRITOMB: return 1450 if ctx["opp_remaining_hp"] and ctx["spiritomb_damage"] >= ctx["opp_remaining_hp"] else 850 + min(400, ctx["spiritomb_damage"])
            if ctx["active_id"] == GARCHOMP_EX:
                heavy = any(token in label for token in ("draconic", "buster", "260"))
                light = any(token in label for token in ("corkscrew", "dive", "100"))
                if heavy: return 1400 if ctx["opp_remaining_hp"] and garchomp_damage(True, ctx["roserade_count"]) >= ctx["opp_remaining_hp"] else 760
                if light: return 1350 if ctx["opp_remaining_hp"] and garchomp_damage(False, ctx["roserade_count"]) >= ctx["opp_remaining_hp"] else 1050
                return 1000
            return 520 if ctx["active_id"] == GABITE else 120
        if kind == T_ABILITY: return 1180 if card == GABITE or ctx["gabite_in_play"] or "champion" in label else 520
        if kind == T_EVOLVE: return 1160 if card == GARCHOMP_EX else 1080 if card == GABITE else 1020 if card == ROSERADE else 400
        if kind == T_ENERGY:
            if target == GARCHOMP_EX: return 1100 if ctx["active_energy"] < 2 else 690
            if target == SPIRITOMB: return 1130 if ctx["opp_remaining_hp"] and ctx["spiritomb_damage"] >= ctx["opp_remaining_hp"] else 760
            if target in {GIBLE, GABITE}: return 920
            return 520
        if kind == T_PLAY:
            if card in {POFFIN, POKE_PAD, FIGHTING_GONG, HILDA}: return 1030 if not ctx["garchomp_in_play"] else 690
            if card == FOREST: return 900 if ctx["roserade_count"] == 0 else 430
            if card == POWER_WEIGHT: return 1000 if target == GARCHOMP_EX else 760 if target in CYNTHIA_POKEMON else 350
            if card == BOSS: return 1020 if ctx["active_id"] in {GARCHOMP_EX, SPIRITOMB} else 280
            if card == UNFAIR_STAMP: return 1060
            if card in {LILLIE, HILDA}: return 850
            if card == XEROSIC: return 730
            if card == SURFER: return 1250 if ctx["active_id"] != SPIRITOMB and ctx["spiritomb_in_play"] and ctx["opp_remaining_hp"] and ctx["spiritomb_damage"] >= ctx["opp_remaining_hp"] else 620
            if card == NIGHT_STRETCHER: return 590
            if card in CYNTHIA_POKEMON: return 900
            return 350
        if kind == T_RETREAT:
            if ctx["active_id"] != SPIRITOMB and ctx["spiritomb_in_play"] and ctx["opp_remaining_hp"] and ctx["spiritomb_damage"] >= ctx["opp_remaining_hp"]: return 1300
            return 900 if ctx["active_id"] != GARCHOMP_EX and ctx["garchomp_in_play"] else 130
        return 0


def build_policy(candidate: str) -> ScoredPolicy:
    if candidate == "mewtwo_spidops": return MewtwoSpidopsPolicy()
    if candidate == "garchomp_spiritomb": return GarchompSpiritombPolicy()
    raise ValueError(f"unknown candidate: {candidate}")

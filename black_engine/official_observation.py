from __future__ import annotations

from copy import deepcopy
from typing import Any


AREA_ACTIVE = 4
AREA_BENCH = 5


def _card_id(value: Any) -> int:
    if type(value) is int:
        return value
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            candidate = value.get(key)
            if type(candidate) is int:
                return candidate
    return -1


def _attached_energy_option(current: dict[str, Any], option: dict[str, Any], actor: int) -> None:
    """Materialize CABT attached-card selections without changing their raw keys.

    Real Erasure Ball follow-up options use only:

    ``type=5, area=5, index=<bench pokemon>, energyIndex=<attached energy>``.

    ``index`` therefore identifies the parent Pokemon, not the Energy card.  Add
    synthetic ``card`` and ``target`` fields to the normalized copy so TruthState
    can expose the selected Energy as ``card_id`` and its holder as ``target_id``.
    The original observation supplied by CABT is never mutated.
    """
    energy_index = option.get("energyIndex")
    area = option.get("area")
    pokemon_index = option.get("index")
    if type(energy_index) is not int or area not in (AREA_ACTIVE, AREA_BENCH) or type(pokemon_index) is not int:
        return

    player_index = option.get("playerIndex", actor)
    if player_index not in (0, 1):
        player_index = actor
    players = current.get("players")
    if not isinstance(players, list) or not (0 <= player_index < len(players)):
        return
    player = players[player_index]
    if not isinstance(player, dict):
        return
    zone_name = "active" if area == AREA_ACTIVE else "bench"
    zone = player.get(zone_name)
    if not isinstance(zone, list) or not (0 <= pokemon_index < len(zone)):
        return
    pokemon = zone[pokemon_index]
    if not isinstance(pokemon, dict):
        return

    energies = None
    for key in ("energyCards", "energies", "energy"):
        value = pokemon.get(key)
        if isinstance(value, list):
            energies = value
            break
    if energies is None or not (0 <= energy_index < len(energies)):
        return

    energy_id = _card_id(energies[energy_index])
    target_id = _card_id(pokemon)
    if energy_id >= 0:
        option.setdefault("card", energy_id)
    if target_id >= 0:
        option.setdefault("target", target_id)


def normalize_official_observation(obs: dict[str, Any]) -> dict[str, Any]:
    """Return a non-destructive CABT-normalized observation.

    The official engine exposes ``hp`` as current remaining HP and ``maxHp``
    as the ceiling. Older BLACK truth code also accepts an explicit ``damage``
    field, so we materialize ``damage=maxHp-hp`` before building TruthState.

    CABT attached-card windows identify each Energy with
    ``area/index/energyIndex`` rather than a direct card ID. These references are
    resolved on the copied observation so all planners see the actual Energy and
    parent Pokemon while the official input remains untouched.
    """
    normalized = deepcopy(obs)
    current = normalized.get("current")
    if not isinstance(current, dict):
        return normalized
    players = current.get("players")
    if isinstance(players, list):
        for player in players:
            if not isinstance(player, dict):
                continue
            for zone_name in ("active", "bench"):
                zone = player.get(zone_name)
                if not isinstance(zone, list):
                    continue
                for pokemon in zone:
                    if not isinstance(pokemon, dict):
                        continue
                    hp = pokemon.get("hp")
                    max_hp = pokemon.get("maxHp")
                    if type(hp) in (int, float) and type(max_hp) in (int, float):
                        pokemon["damage"] = max(0, int(max_hp) - int(hp))

    actor = current.get("yourIndex", 0)
    actor = actor if actor in (0, 1) else 0
    select = normalized.get("select")
    if isinstance(select, dict):
        options = select.get("option")
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict):
                    _attached_energy_option(current, option, actor)
    return normalized

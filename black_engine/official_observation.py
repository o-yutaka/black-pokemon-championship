from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_official_observation(obs: dict[str, Any]) -> dict[str, Any]:
    """Return a non-destructive CABT-normalized observation.

    The official engine exposes ``hp`` as current remaining HP and ``maxHp``
    as the ceiling.  Older BLACK truth code also accepts an explicit
    ``damage`` field, so we materialize ``damage=maxHp-hp`` before building
    TruthState.  This keeps replay/source compatibility without mutating the
    object supplied by Kaggle.
    """
    normalized = deepcopy(obs)
    current = normalized.get("current")
    if not isinstance(current, dict):
        return normalized
    players = current.get("players")
    if not isinstance(players, list):
        return normalized
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
    return normalized

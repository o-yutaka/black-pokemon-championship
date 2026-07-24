from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .support import card_id, max_hp, my_index, remaining_hp

AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH = 1, 2, 3, 4, 5
AREA_ENERGY = 8
T_PLAY, T_ENERGY, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK = 7, 8, 9, 10, 12, 13

TEAM_ROCKET_ENERGY = 15
PSYCHIC_ENERGY = 5
BASIC_ENERGY_IDS = frozenset(range(1, 10))


def _serial(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("serial")
    return raw if type(raw) is int else None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _players(current: dict) -> list:
    return _list(current.get("players"))


def _player(current: dict, index: int) -> dict:
    values = _players(current)
    if 0 <= index < len(values) and isinstance(values[index], dict):
        return values[index]
    return {}


def _zone(current: dict, select: dict, player_index: int, area: int | None) -> list:
    if area == AREA_DECK:
        return _list(select.get("deck"))
    player = _player(current, player_index)
    key = {
        AREA_HAND: "hand",
        AREA_DISCARD: "discard",
        AREA_ACTIVE: "active",
        AREA_BENCH: "bench",
    }.get(area)
    if key is not None:
        return _list(player.get(key))
    return []


def _in_play_value(current: dict, player_index: int, area: Any, slot: Any) -> dict | None:
    if type(area) is not int or type(slot) is not int or area not in {AREA_ACTIVE, AREA_BENCH}:
        return None
    values = _zone(current, {}, player_index, area)
    if 0 <= slot < len(values) and isinstance(values[slot], dict):
        return values[slot]
    return None


def _explicit_int(raw: dict, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = raw.get(key)
        if type(value) is int:
            return value
    return None


@dataclass(frozen=True)
class PokemonInstance:
    player_index: int
    serial: int
    card_id: int
    area: int
    slot: int
    current_hp: int
    max_hp: int
    energy_card_ids: tuple[int, ...]
    energy_card_serials: tuple[int, ...]

    @property
    def key(self) -> tuple[int, int]:
        return (self.player_index, self.serial)

    @property
    def damage(self) -> int:
        return max(0, self.max_hp - self.current_hp)

    @property
    def psychic_units(self) -> int:
        return sum(card == PSYCHIC_ENERGY for card in self.energy_card_ids) + 2 * sum(
            card == TEAM_ROCKET_ENERGY for card in self.energy_card_ids
        )

    @property
    def total_energy_units(self) -> int:
        return len(self.energy_card_ids) + sum(card == TEAM_ROCKET_ENERGY for card in self.energy_card_ids)


@dataclass(frozen=True)
class MewtwoOption:
    action_index: int
    action_type: int
    card_id: int
    attack_id: int
    source_serial: int | None
    target_serial: int | None
    energy_card_id: int | None
    energy_source_serial: int | None
    raw: dict


@dataclass(frozen=True)
class MewtwoTruth:
    actor: int
    opponent: int
    turn: int
    context: int
    minimum: int
    maximum: int
    mine: tuple[PokemonInstance, ...]
    theirs: tuple[PokemonInstance, ...]
    hand_ids: tuple[int, ...]
    discard_ids: tuple[int, ...]
    opponent_hand_count: int
    our_prizes: int
    opponent_prizes: int
    supporter_played: bool
    options: tuple[MewtwoOption, ...]
    effect_card_id: int
    raw_observation: dict

    @property
    def active(self) -> PokemonInstance | None:
        return next((value for value in self.mine if value.area == AREA_ACTIVE), None)

    @property
    def opponent_active(self) -> PokemonInstance | None:
        return next((value for value in self.theirs if value.area == AREA_ACTIVE), None)

    def by_serial(self, player_index: int, serial: int | None) -> PokemonInstance | None:
        if serial is None:
            return None
        pool = self.mine if player_index == self.actor else self.theirs
        return next((value for value in pool if value.serial == serial), None)


def _energy_cards(value: dict) -> tuple[tuple[int, ...], tuple[int, ...]]:
    ids: list[int] = []
    serials: list[int] = []
    for item in _list(value.get("energyCards")):
        cid = card_id(item)
        if cid >= 0:
            ids.append(cid)
            serials.append(_serial(item) if _serial(item) is not None else -1)
    return tuple(ids), tuple(serials)


def _instances(current: dict, player_index: int) -> tuple[PokemonInstance, ...]:
    result: list[PokemonInstance] = []
    for area, key in ((AREA_ACTIVE, "active"), (AREA_BENCH, "bench")):
        for slot, value in enumerate(_list(_player(current, player_index).get(key))):
            if not isinstance(value, dict):
                continue
            serial = _serial(value)
            cid = card_id(value)
            if serial is None or cid < 0:
                continue
            energy_ids, energy_serials = _energy_cards(value)
            result.append(
                PokemonInstance(
                    player_index=player_index,
                    serial=serial,
                    card_id=cid,
                    area=area,
                    slot=slot,
                    current_hp=remaining_hp(value),
                    max_hp=max_hp(value),
                    energy_card_ids=energy_ids,
                    energy_card_serials=energy_serials,
                )
            )
    return tuple(result)


def _resolve_zone_card(current: dict, select: dict, player_index: int, area: Any, index: Any) -> int:
    if type(area) is not int or type(index) is not int:
        return -1
    values = _zone(current, select, player_index, area)
    if 0 <= index < len(values):
        return card_id(values[index])
    return -1


def _resolve_in_play_serial(current: dict, player_index: int, raw: dict) -> int | None:
    value = _in_play_value(current, player_index, raw.get("inPlayArea"), raw.get("inPlayIndex"))
    return _serial(value)


def _resolve_energy_selection(
    current: dict,
    actor: int,
    raw: dict,
) -> tuple[int | None, int | None]:
    player_index = raw.get("playerIndex", actor)
    if type(player_index) is not int or player_index not in (0, 1):
        player_index = actor
    pokemon = _in_play_value(current, player_index, raw.get("inPlayArea"), raw.get("inPlayIndex"))
    if not isinstance(pokemon, dict):
        return None, None
    energy_index = raw.get("energyIndex")
    cards = _list(pokemon.get("energyCards"))
    if type(energy_index) is int and 0 <= energy_index < len(cards):
        cid = card_id(cards[energy_index])
        return (cid if cid >= 0 else None), _serial(pokemon)
    return None, _serial(pokemon)


def _option(raw_value: Any, action_index: int, current: dict, select: dict, actor: int) -> MewtwoOption:
    raw = raw_value if isinstance(raw_value, dict) else {}
    action_type = raw.get("type") if type(raw.get("type")) is int else -1
    player_index = raw.get("playerIndex", actor)
    if type(player_index) is not int or player_index not in (0, 1):
        player_index = actor

    cid = -1
    for key in ("card", "cardId", "id"):
        candidate = card_id(raw.get(key))
        if candidate >= 0:
            cid = candidate
            break
    area = raw.get("area")
    if area is None and action_type == T_PLAY:
        area = AREA_HAND
    if cid < 0:
        cid = _resolve_zone_card(current, select, player_index, area, raw.get("index"))

    attack = raw.get("attack")
    attack_id = -1
    if isinstance(attack, dict):
        attack_id = attack.get("attackId") if type(attack.get("attackId")) is int else attack.get("id", -1)
    if type(attack_id) is not int or attack_id < 0:
        attack_id = raw.get("attackId") if type(raw.get("attackId")) is int else -1

    source_serial = _explicit_int(raw, ("sourceSerial",))
    target_serial = _explicit_int(raw, ("targetSerial", "pokemonSerial", "toSerial"))
    in_play_serial = _resolve_in_play_serial(current, player_index, raw)

    if action_type in {T_ATTACK, T_ABILITY, T_RETREAT}:
        source_serial = source_serial if source_serial is not None else _explicit_int(raw, ("serial",))
        source_serial = source_serial if source_serial is not None else in_play_serial
        if cid < 0 and source_serial is not None:
            source_value = next(
                (value for value in _instances(current, player_index) if value.serial == source_serial),
                None,
            )
            cid = source_value.card_id if source_value is not None else cid
    else:
        target_serial = target_serial if target_serial is not None else _explicit_int(raw, ("serial",))
        target_serial = target_serial if target_serial is not None else in_play_serial

    energy_card_id, energy_source_serial = _resolve_energy_selection(current, actor, raw)
    if cid < 0 and energy_card_id is not None:
        cid = energy_card_id

    return MewtwoOption(
        action_index=action_index,
        action_type=action_type,
        card_id=cid,
        attack_id=attack_id,
        source_serial=source_serial,
        target_serial=target_serial,
        energy_card_id=energy_card_id,
        energy_source_serial=energy_source_serial,
        raw=raw,
    )


def _prize_count(player: dict) -> int:
    for key in ("prizeCount", "remainingPrizeCount", "remainingPrizes"):
        value = player.get(key)
        if type(value) is int:
            return max(0, value)
    return len(_list(player.get("prize")))


def build_mewtwo_truth(obs: dict) -> MewtwoTruth:
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    actor = my_index(obs)
    opponent = 1 - actor
    my_player = _player(current, actor)
    their_player = _player(current, opponent)
    effect = card_id(select.get("effect"))
    return MewtwoTruth(
        actor=actor,
        opponent=opponent,
        turn=int(current.get("turn", current.get("turnCount", 0)) or 0),
        context=int(select.get("context", -1) or -1),
        minimum=max(0, int(select.get("minCount", 1) or 0)),
        maximum=max(0, int(select.get("maxCount", 1) or 0)),
        mine=_instances(current, actor),
        theirs=_instances(current, opponent),
        hand_ids=tuple(card_id(value) for value in _list(my_player.get("hand")) if card_id(value) >= 0),
        discard_ids=tuple(card_id(value) for value in _list(my_player.get("discard")) if card_id(value) >= 0),
        opponent_hand_count=int(their_player.get("handCount", len(_list(their_player.get("hand")))) or 0),
        our_prizes=_prize_count(my_player),
        opponent_prizes=_prize_count(their_player),
        supporter_played=bool(my_player.get("supporterPlayed", False)),
        options=tuple(
            _option(value, index, current, select, actor)
            for index, value in enumerate(_list(select.get("option")))
        ),
        effect_card_id=effect,
        raw_observation=obs,
    )

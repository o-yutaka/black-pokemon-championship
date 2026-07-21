from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..support import active, bench, card_id, damage_points, in_play, my_index, remaining_hp


@dataclass(frozen=True)
class PokemonRef:
    player_index: int
    serial: int
    card_id: int
    area: int
    slot: int
    hp: int
    damage: int
    energy_card_ids: tuple[int, ...]


@dataclass(frozen=True)
class BoardVision:
    me: int
    opponent: int
    mine: tuple[PokemonRef, ...]
    theirs: tuple[PokemonRef, ...]
    active_serial: int | None
    opponent_active_serial: int | None
    opponent_board_damage: int
    unknown_fields: tuple[str, ...]

    def mine_by_card(self, cid: int) -> tuple[PokemonRef, ...]:
        return tuple(ref for ref in self.mine if ref.card_id == cid)

    def theirs_by_card(self, cid: int) -> tuple[PokemonRef, ...]:
        return tuple(ref for ref in self.theirs if ref.card_id == cid)


def _serial(value: dict[str, Any]) -> int:
    serial = value.get("serial")
    return serial if type(serial) is int else -1


def _energy_ids(value: dict[str, Any]) -> tuple[int, ...]:
    cards = value.get("energyCards")
    if not isinstance(cards, list):
        return ()
    return tuple(card_id(card) for card in cards if card_id(card) >= 0)


def _refs(obs: dict, player_index: int) -> tuple[PokemonRef, ...]:
    values = in_play(obs, player_index)
    active_value = active(obs, player_index)
    bench_values = bench(obs, player_index)
    active_serial = _serial(active_value) if isinstance(active_value, dict) else -1
    bench_serial_to_slot = {
        _serial(value): slot for slot, value in enumerate(bench_values) if isinstance(value, dict)
    }
    result: list[PokemonRef] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        serial = _serial(value)
        if serial == active_serial:
            area, slot = 4, 0
        else:
            area, slot = 5, bench_serial_to_slot.get(serial, -1)
        result.append(
            PokemonRef(
                player_index=player_index,
                serial=serial,
                card_id=card_id(value),
                area=area,
                slot=slot,
                hp=max(0, remaining_hp(value)),
                damage=max(0, damage_points(value)),
                energy_card_ids=_energy_ids(value),
            )
        )
    return tuple(result)


def build_board_vision(obs: dict) -> BoardVision:
    me = my_index(obs)
    opponent = 1 - me
    mine = _refs(obs, me)
    theirs = _refs(obs, opponent)
    my_active = active(obs, me)
    their_active = active(obs, opponent)
    unknown: list[str] = []
    current = obs.get("current") if isinstance(obs.get("current"), dict) else {}
    if not isinstance(current.get("players"), list):
        unknown.append("players")
    return BoardVision(
        me=me,
        opponent=opponent,
        mine=mine,
        theirs=theirs,
        active_serial=_serial(my_active) if isinstance(my_active, dict) else None,
        opponent_active_serial=_serial(their_active) if isinstance(their_active, dict) else None,
        opponent_board_damage=sum(ref.damage for ref in theirs),
        unknown_fields=tuple(unknown),
    )

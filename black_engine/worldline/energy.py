from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnergyTruth:
    physical_card_ids: tuple[int, ...]
    effective_units: int
    effective_types: tuple[int, ...]


TEAM_ROCKET_ENERGY = -1


def count_effective_units(card_ids: tuple[int, ...], double_unit_ids: frozenset[int] = frozenset()) -> int:
    return sum(2 if card_id in double_unit_ids else 1 for card_id in card_ids)


def build_energy_truth(card_ids: tuple[int, ...], double_unit_ids: frozenset[int] = frozenset()) -> EnergyTruth:
    return EnergyTruth(
        physical_card_ids=card_ids,
        effective_units=count_effective_units(card_ids, double_unit_ids),
        effective_types=card_ids,
    )

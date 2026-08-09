from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DecisionPoint:
    option_index: int
    option: dict[str, Any]
    action_type: int | None
    card_id: int | None
    target_id: int | None
    semantic: str


def _first_int(option: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = option.get(key)
        if type(value) is int:
            return value
    return None


def build_decision_points(obs: dict[str, Any]) -> list[DecisionPoint]:
    """Normalize every engine-provided option without deciding which one wins."""
    select = obs.get("select")
    options = select.get("option") if isinstance(select, dict) else None
    if not isinstance(options, list):
        return []

    points: list[DecisionPoint] = []
    for index, raw in enumerate(options):
        option = raw if isinstance(raw, dict) else {"raw": raw}
        action_type = option.get("type") if type(option.get("type")) is int else None
        points.append(
            DecisionPoint(
                option_index=index,
                option=option,
                action_type=action_type,
                card_id=_first_int(option, ("cardId", "card", "id")),
                target_id=_first_int(option, ("target", "pokemon", "to", "selectPokemon")),
                semantic=f"type:{action_type}" if action_type is not None else "unknown",
            )
        )
    return points

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Iterable, Mapping


class EngineSourceSafetyError(RuntimeError):
    pass


def align_visualizer_selected(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Repair the documented one-step visualizer selected-action shift.

    The state at index i receives the selection serialized at index i+1.
    The terminal dummy record is retained with selected=None. Input is never
    mutated. This helper is for offline analysis/training only.
    """
    rows = [deepcopy(dict(row)) for row in records]
    if not rows:
        return []
    for index in range(len(rows) - 1):
        rows[index]["selected"] = deepcopy(rows[index + 1].get("selected"))
    rows[-1]["selected"] = None
    return rows


def team_rocket_energy_attach_is_safe(
    option: Mapping[str, Any],
    *,
    resolve_card: Callable[[Mapping[str, Any]], Mapping[str, Any] | None],
    resolve_target: Callable[[Mapping[str, Any]], Mapping[str, Any] | None],
) -> bool:
    """Fail closed for the reported onlyTeamRocket attachment crash path.

    The guard does not alter the engine. It rejects an attachment whenever the
    attached card is marked onlyTeamRocket and the resolved target is not a
    Team Rocket Pokemon. Missing metadata is treated as unsafe for such cards.
    """
    card = resolve_card(option)
    if not isinstance(card, Mapping) or not bool(card.get("onlyTeamRocket", False)):
        return True
    target = resolve_target(option)
    return isinstance(target, Mapping) and bool(target.get("teamRocket", False))


def require_competition_use_notice(text: str) -> None:
    required = (
        "competition",
        "local development",
        "testing",
        "validation",
        "benchmarking",
    )
    lowered = text.lower()
    missing = [token for token in required if token not in lowered]
    if missing:
        raise EngineSourceSafetyError(
            "engine license/notice is missing required competition-use markers: "
            + ", ".join(missing)
        )

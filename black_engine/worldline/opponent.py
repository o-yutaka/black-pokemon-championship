from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpponentPain:
    routes_removed: int = 0
    attacks_added: int = 0
    forced_resources: int = 0
    target_conflict: int = 0
    best_response_value: float = 0.0

    @property
    def score(self) -> float:
        return (
            1000 * self.routes_removed
            + 600 * self.attacks_added
            + 120 * self.forced_resources
            + 180 * self.target_conflict
            - self.best_response_value
        )

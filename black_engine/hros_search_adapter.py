from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SearchVerification:
    option_index: int
    verified: bool
    score_delta: float = 0.0
    transition: dict[str, Any] | None = None
    opponent_response: Any = None


class HROSSearchAdapter:
    """Optional bridge to the external HROS official-engine verifier.

    This module intentionally has no HROS import and cannot execute actions by
    itself. The championship runtime remains legal-option authoritative. A
    configured verifier receives only currently exposed option indexes and may
    return evidence for candidate re-ranking.
    """

    def __init__(self, verifier: Callable[[dict[str, Any], list[int]], Any] | None = None) -> None:
        self._verifier = verifier

    @property
    def available(self) -> bool:
        return callable(self._verifier)

    def verify(self, obs: dict[str, Any], option_indexes: list[int]) -> Any:
        if not self.available or not option_indexes:
            return None
        return self._verifier(obs, list(option_indexes))

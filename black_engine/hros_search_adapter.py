from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TransitionEvidence:
    option_index: int
    accepted: bool
    before_hash: str | None = None
    after_hash: str | None = None
    opponent_response: Any = None
    details: dict[str, Any] | None = None


class HROSSearchAdapter:
    """Optional bridge; the CABT option list remains the legal-action authority."""

    def __init__(self, verifier: Callable[[dict[str, Any], list[int]], Any] | None = None) -> None:
        self._verifier = verifier

    @property
    def available(self) -> bool:
        return callable(self._verifier)

    def verify(self, obs: dict[str, Any], option_indexes: list[int]) -> Any:
        if not self.available or not option_indexes:
            return None
        return self._verifier(obs, list(option_indexes))

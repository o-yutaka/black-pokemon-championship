from __future__ import annotations

import dataclasses
import importlib
import os
import sys
from pathlib import Path
from typing import Any

from .belief import Determinization
from .ismcts import SearchFrame
from .truth import TruthState


def _object_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"cannot convert SearchState to dict: {type(value)!r}")


def _extract_search_id(state: Any) -> int:
    mapping = _object_dict(state)
    for key in ("searchId", "search_id", "id"):
        value = mapping.get(key)
        if type(value) is int:
            return value
    raise RuntimeError(f"SearchState missing search ID: keys={sorted(mapping)}")


def _extract_observation(state: Any) -> dict:
    mapping = _object_dict(state)
    for key in ("observation", "obs", "agentObservation", "agent_observation"):
        value = mapping.get(key)
        if isinstance(value, dict):
            return value
        if value is not None:
            return _object_dict(value)
    if "current" in mapping and "select" in mapping:
        return mapping
    raise RuntimeError(f"SearchState missing observation: keys={sorted(mapping)}")


def _extract_result(state: Any, observation: dict) -> int:
    mapping = _object_dict(state)
    for key in ("result", "winner"):
        value = mapping.get(key)
        if type(value) is int:
            return value
    current = observation.get("current") if isinstance(observation.get("current"), dict) else {}
    value = current.get("result", -1)
    return value if type(value) is int else -1


class CabtSearchAdapter:
    """Adapter for the documented `cg.api` Search API."""

    def __init__(self, cg_dir: str | Path | None = None) -> None:
        explicit = Path(cg_dir).resolve() if cg_dir else None
        if explicit:
            parent = str(explicit.parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
        elif os.environ.get("CABT_CG_DIR"):
            parent = str(Path(os.environ["CABT_CG_DIR"]).resolve().parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
        importlib.invalidate_caches()
        self.api = importlib.import_module("cg.api")
        required = ("search_begin", "search_step", "search_release", "search_end")
        missing = [name for name in required if not callable(getattr(self.api, name, None))]
        if missing:
            raise RuntimeError(f"cg.api missing documented Search API: {missing}")

    def _frame(self, state: Any) -> SearchFrame:
        observation = _extract_observation(state)
        return SearchFrame(
            search_id=_extract_search_id(state),
            observation=observation,
            terminal_result=_extract_result(state, observation),
        )

    def begin(self, truth: TruthState, determinization: Determinization) -> SearchFrame:
        observation: Any = truth.raw_observation
        converter = getattr(self.api, "to_observation_class", None)
        if callable(converter):
            observation = converter(observation)
        state = self.api.search_begin(
            observation,
            list(determinization.your_deck),
            list(determinization.your_prize),
            list(determinization.opponent_deck),
            list(determinization.opponent_prize),
            list(determinization.opponent_hand),
            list(determinization.opponent_active),
            False,
        )
        return self._frame(state)

    def step(self, search_id: int, selection: list[int]) -> SearchFrame:
        return self._frame(self.api.search_step(search_id, selection))

    def release(self, search_id: int) -> None:
        self.api.search_release(search_id)

    def end(self) -> None:
        self.api.search_end()

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .official_runtime import EngineUnavailable, locate_cg_dir


@dataclass(frozen=True)
class SearchCapability:
    available: bool
    source: str
    lifecycle: tuple[str, ...]
    reason: str = ""


def inspect_search_capability(cg_dir: str | Path | None = None) -> SearchCapability:
    """Inspect only documented official Search API names.

    No hidden enemy hand/deck/prize access is assumed. Search is restricted to
    SearchBegin/SearchStep/SearchRelease/SearchEnd state-transition exploration.
    """
    directory = locate_cg_dir(cg_dir)
    parent = str(directory.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    importlib.invalidate_caches()
    try:
        sim = importlib.import_module("cg.sim")
    except Exception as exc:
        return SearchCapability(False, "cg.sim", (), f"import failed: {exc}")

    snake = ("search_begin", "search_step", "search_release", "search_end")
    if all(callable(getattr(sim, name, None)) for name in snake):
        return SearchCapability(True, "cg.sim", snake)

    native = ("SearchBegin", "SearchStep", "SearchRelease", "SearchEnd")
    if all(getattr(sim, name, None) is not None for name in native):
        return SearchCapability(True, "cg.sim ctypes bindings", native)

    return SearchCapability(
        False,
        "cg.sim",
        (),
        "documented Search lifecycle is not exposed by this local wrapper",
    )


class OfficialSearchSession:
    """Fail-closed adapter for high-level documented search functions.

    This class intentionally does not call raw ctypes signatures because those
    must match the exact local wrapper/binary provenance. A local HROS-specific
    cg_search_api wrapper may be connected separately after its hash gate passes.
    """

    def __init__(self, cg_dir: str | Path | None = None) -> None:
        capability = inspect_search_capability(cg_dir)
        if not capability.available or capability.lifecycle[0] != "search_begin":
            raise EngineUnavailable(
                f"high-level official Search API unavailable: {capability.reason or capability.source}"
            )
        directory = locate_cg_dir(cg_dir)
        parent = str(directory.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        self._sim = importlib.import_module("cg.sim")
        self._active = False

    def begin(self, *args: Any, **kwargs: Any):
        if self._active:
            raise RuntimeError("search session already active")
        result = self._sim.search_begin(*args, **kwargs)
        self._active = True
        return result

    def step(self, search_id: int, selection: list[int]):
        if not self._active:
            raise RuntimeError("search session is not active")
        return self._sim.search_step(search_id, selection)

    def release(self, search_id: int):
        if self._active:
            return self._sim.search_release(search_id)
        return None

    def close(self):
        if self._active:
            self._active = False
            return self._sim.search_end()
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

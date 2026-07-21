from __future__ import annotations

from collections.abc import Callable, Iterable

from .judge import CausalJudge
from .model import WorldlineResult
from .vision import BoardVision

Runner = Callable[[dict, BoardVision], Iterable[WorldlineResult]]


class RunnerArena:
    def __init__(self, runners: Iterable[Runner], judge: CausalJudge | None = None):
        self.runners = tuple(runners)
        self.judge = judge or CausalJudge()

    def evaluate(self, obs: dict, vision: BoardVision) -> list[WorldlineResult]:
        results: list[WorldlineResult] = []
        for runner in self.runners:
            produced = runner(obs, vision)
            results.extend(produced)
        return results

    def choose(self, obs: dict, vision: BoardVision) -> WorldlineResult:
        return self.judge.choose(self.evaluate(obs, vision))

from __future__ import annotations

from .model import PendingPlan


class PendingPlanStore:
    def __init__(self) -> None:
        self._plan: PendingPlan | None = None

    def get(self) -> PendingPlan | None:
        return self._plan

    def set(self, plan: PendingPlan) -> None:
        self._plan = plan

    def clear(self) -> None:
        self._plan = None

    def invalidate(self, reason: str) -> None:
        if self._plan is not None:
            self._plan.abort(reason)
        self._plan = None

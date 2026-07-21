from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import WorldlineResult


def runner_trace(results: list[WorldlineResult], selected_plan_id: str) -> dict[str, Any]:
    return {
        "available_runner_ids": [result.plan.plan_id for result in results],
        "selected_runner": selected_plan_id,
        "runner_results": [asdict(result) for result in results],
    }

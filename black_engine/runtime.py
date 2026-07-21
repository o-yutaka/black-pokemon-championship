from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeDecision:
    selection: list[int]
    source: str
    elapsed_ms: float
    error: str | None = None


def _is_deck_request(obs: Any) -> bool:
    return (
        isinstance(obs, dict)
        and obs.get("current") is None
        and obs.get("select") is None
    )


def _selection_contract(obs: dict) -> tuple[int, int, int]:
    select = obs.get("select") or {}
    options = select.get("option") or []
    minimum = int(select.get("minCount", 0) or 0)
    maximum_raw = select.get("maxCount", minimum)
    maximum = minimum if maximum_raw is None else int(maximum_raw)
    return minimum, maximum, len(options)


def legalize_selection(obs: dict, value: Any) -> list[int] | None:
    minimum, maximum, option_count = _selection_contract(obs)
    if isinstance(value, int) and not isinstance(value, bool):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return None
    if any(not isinstance(index, int) or isinstance(index, bool) for index in values):
        return None
    if len(values) != len(set(values)):
        return None
    if not minimum <= len(values) <= maximum:
        return None
    if any(index < 0 or index >= option_count for index in values):
        return None
    return values


def deterministic_fallback(obs: dict) -> list[int]:
    minimum, maximum, option_count = _selection_contract(obs)
    if minimum == 0:
        return []
    count = min(maximum, option_count)
    if count < minimum:
        return []
    return list(range(option_count - count, option_count))


class SubmissionRuntime:
    def __init__(self, policy: Any, deck: list[int], *, budget_ms: float = 500.0) -> None:
        self.policy = policy
        self.deck = [int(card) for card in deck]
        self.budget_ms = max(1.0, float(budget_ms))
        if hasattr(policy, "set_deck"):
            policy.set_deck(self.deck)

    def decide(self, obs: dict | None, configuration=None) -> RuntimeDecision:
        started = time.perf_counter()
        if _is_deck_request(obs):
            return RuntimeDecision(
                list(self.deck),
                "deck",
                (time.perf_counter() - started) * 1000.0,
            )
        if not isinstance(obs, dict):
            return RuntimeDecision(
                [],
                "invalid_observation",
                (time.perf_counter() - started) * 1000.0,
                "observation_not_dict",
            )
        if obs.get("select") is None:
            return RuntimeDecision(
                [],
                "no_select",
                (time.perf_counter() - started) * 1000.0,
            )

        error = None
        try:
            proposed = self.policy.agent(obs, configuration)
            elapsed = (time.perf_counter() - started) * 1000.0
            legal = legalize_selection(obs, proposed)
            if legal is not None and elapsed <= self.budget_ms:
                return RuntimeDecision(legal, "policy", elapsed)
            error = "timeout" if elapsed > self.budget_ms else "invalid_selection"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        return RuntimeDecision(
            deterministic_fallback(obs),
            "fallback",
            (time.perf_counter() - started) * 1000.0,
            error,
        )

    def agent(self, obs: dict | None, configuration=None) -> list[int]:
        return self.decide(obs, configuration).selection

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


def _selection_contract(obs: dict) -> tuple[int, int, int]:
    select = obs.get("select") or {}
    options = select.get("option") or []
    minimum = int(select.get("minCount", 0) or 0)
    maximum = int(select.get("maxCount", minimum) or minimum)
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
    # Highest indices match the deterministic tie-break used by black_lab and
    # HybridJudge. Keeping one convention avoids evaluation-only drift.
    return list(range(option_count - count, option_count))


class OfficialHybridRuntime:
    """Fail-closed adapter for the official Kaggle agent contract.

    Hybrid decisions are accepted only when they satisfy the exact current
    Observation.select contract. Any exception, timeout, or malformed output
    falls back to the deterministic base policy; a final legal deterministic
    fallback prevents an invalid option index from reaching libcg.
    """

    def __init__(self, hybrid_policy: Any, base_policy: Any, deck: list[int], *, budget_ms: float = 500.0) -> None:
        self.hybrid_policy = hybrid_policy
        self.base_policy = base_policy
        self.deck = [int(card) for card in deck]
        self.budget_ms = max(1.0, float(budget_ms))
        for policy in (hybrid_policy, base_policy):
            if hasattr(policy, "set_deck"):
                policy.set_deck(self.deck)

    def decide(self, obs: dict | None, configuration=None) -> RuntimeDecision:
        started = time.perf_counter()
        if not isinstance(obs, dict) or obs.get("select") is None:
            return RuntimeDecision(list(self.deck), "deck", (time.perf_counter() - started) * 1000.0)

        hybrid_error: str | None = None
        try:
            proposed = self.hybrid_policy.agent(obs, configuration)
            elapsed = (time.perf_counter() - started) * 1000.0
            legal = legalize_selection(obs, proposed)
            if legal is not None and elapsed <= self.budget_ms:
                return RuntimeDecision(legal, "hybrid", elapsed)
            hybrid_error = "timeout" if elapsed > self.budget_ms else "invalid_selection"
        except Exception as exc:  # submission boundary must never leak policy errors
            hybrid_error = f"{type(exc).__name__}: {exc}"

        try:
            proposed = self.base_policy.agent(obs, configuration)
            legal = legalize_selection(obs, proposed)
            if legal is not None:
                return RuntimeDecision(legal, "base_fallback", (time.perf_counter() - started) * 1000.0, hybrid_error)
        except Exception as exc:
            hybrid_error = f"{hybrid_error}; base={type(exc).__name__}: {exc}"

        return RuntimeDecision(
            deterministic_fallback(obs),
            "deterministic_fallback",
            (time.perf_counter() - started) * 1000.0,
            hybrid_error,
        )

    def agent(self, obs: dict | None, configuration=None) -> list[int]:
        return self.decide(obs, configuration).selection

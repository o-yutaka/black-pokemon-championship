from __future__ import annotations

from collections import Counter
from typing import Iterable

CANONICAL_FAILURE_CODES = (
    "LETHAL_MISS",
    "BAD_SPREAD_TARGET",
    "ENERGY_ATTACH_ERROR",
    "TERMINAL_MISS",
    "PROMOTION_ERROR",
)

DETAIL_TO_CANONICAL = {
    "LETHAL_ACTION_MISS": "LETHAL_MISS",
    "SPREAD_TARGET_REGRET": "BAD_SPREAD_TARGET",
    "ENERGY_ATTACH_SUBOPTIMAL": "ENERGY_ATTACH_ERROR",
    "TERMINAL_ACTION_MISS": "TERMINAL_MISS",
    "PROMOTION_LETHAL_MISS": "PROMOTION_ERROR",
    "PRIZE_AWARE_ACTIVE_MISS": "PROMOTION_ERROR",
}


def canonical_failure_code(detail_code: str) -> str | None:
    return DETAIL_TO_CANONICAL.get(detail_code)


def canonical_failure_counts(detail_codes: Iterable[str]) -> dict[str, int]:
    counts: Counter[str] = Counter({code: 0 for code in CANONICAL_FAILURE_CODES})
    for detail in detail_codes:
        canonical = canonical_failure_code(detail)
        if canonical is not None:
            counts[canonical] += 1
    return {code: counts[code] for code in CANONICAL_FAILURE_CODES}

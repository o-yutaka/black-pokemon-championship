from __future__ import annotations

import math
from collections.abc import Iterable


def wilson_interval(wins: int, games: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if games <= 0:
        return (0.0, 0.0)
    wins = max(0, min(int(wins), int(games)))
    n = float(games)
    p = wins / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def percentile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    q = max(0.0, min(1.0, float(q)))
    position = q * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction

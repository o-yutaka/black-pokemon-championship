from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CYCLE_REASONS = {"RESOURCE_LOSS_CYCLE", "SWITCH_BACK_LOOP"}


def rejected_option_indexes(overlay: Mapping[str, Any] | None) -> set[int]:
    """Return option indexes rejected by real search evidence.

    Only explicit optionIndex values with a known cycle reason are trusted.
    Missing reasons or display-only labels never become action guards.
    """
    if not isinstance(overlay, Mapping):
        return set()
    result: set[int] = set()
    branches = overlay.get("rejectedBranches")
    if not isinstance(branches, Sequence) or isinstance(branches, (str, bytes, bytearray)):
        return result
    for branch in branches:
        if not isinstance(branch, Mapping):
            continue
        reason = str(branch.get("reason", "")).upper()
        index = branch.get("optionIndex")
        if reason in CYCLE_REASONS and isinstance(index, int) and not isinstance(index, bool) and index >= 0:
            result.add(index)
    return result


def choose_search_safe_single(selection: Sequence[int], scores: Sequence[float], blocked: set[int]) -> list[int]:
    """Replace a blocked single selection with the highest-scoring safe option.

    Multi-select decisions and decisions without an explicit search rejection are
    left unchanged. If every option is blocked, the original selection is kept so
    the normal legality/fallback layer remains authoritative.
    """
    chosen = list(selection)
    if len(chosen) != 1 or not isinstance(chosen[0], int) or chosen[0] not in blocked:
        return chosen
    safe = [(float(score), index) for index, score in enumerate(scores) if index not in blocked]
    if not safe:
        return chosen
    return [max(safe, key=lambda row: (row[0], row[1]))[1]]

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _candidate_roots() -> list[Path]:
    """Return portable bundle-root candidates without assuming ``__file__`` exists."""
    candidates: list[Path] = [Path.cwd()]

    explicit = os.environ.get("BLACK_BUNDLE_ROOT")
    if explicit:
        candidates.insert(0, Path(explicit))

    # Kaggle CABT evaluates raw Python with exec(code_object, env), so __file__
    # may be absent. Reading it through globals() is optional compatibility only.
    module_file = globals().get("__file__")
    if isinstance(module_file, str) and module_file:
        candidates.append(Path(module_file).resolve().parent)

    # Reuse import roots supplied by the runtime instead of hard-coding Kaggle
    # or local absolute paths.
    for entry in sys.path:
        if isinstance(entry, str) and entry:
            candidates.append(Path(entry))

    return candidates


def _find_bundle_root() -> Path:
    seen: set[Path] = set()
    for candidate in _candidate_roots():
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / name).is_file() for name in ("main.py", "deck.csv", "submission_contract.py")):
            return candidate

    raise RuntimeError(
        "submission bundle root not found; checked: "
        + ", ".join(str(path) for path in seen)
    )


ROOT = _find_bundle_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from submission_contract import validate_runtime_layout

validate_runtime_layout(ROOT)

from black_engine import DragapultPolicy, SubmissionRuntime, read_deck
from black_engine.search_guard import choose_search_safe_single, rejected_option_indexes


class SearchGuardedDragapultPolicy(DragapultPolicy):
    """Apply explicit official Search cycle evidence to the final single action.

    The underlying policy still creates the full Decision IDE trace. This layer
    only overrides a selected option when the official Search API explicitly
    reports RESOURCE_LOSS_CYCLE/SWITCH_BACK_LOOP for that exact option index.
    """

    def agent(self, obs: dict | None, configuration: Any = None):
        selection = super().agent(obs, configuration)
        if not isinstance(obs, dict) or obs.get("select") is None:
            return selection
        overlay = self.get_decision_overlay()
        blocked = rejected_option_indexes(overlay)
        if not blocked:
            return selection
        options = (obs.get("select") or {}).get("option") or []
        if not isinstance(options, list):
            return selection
        context = self.build_context(obs)
        scores = [float(self.score_option(option, context)) if isinstance(option, dict) else -1e9 for option in options]
        guarded = choose_search_safe_single(selection, scores, blocked)
        if guarded == list(selection):
            return selection

        guarded_index = guarded[0]
        updated = dict(overlay or {})
        candidates = [dict(candidate) for candidate in updated.get("candidates", []) if isinstance(candidate, dict)]
        for index, candidate in enumerate(candidates):
            candidate["selected"] = index == guarded_index
        updated["candidates"] = candidates
        if 0 <= guarded_index < len(candidates):
            candidate = candidates[guarded_index]
            updated["chosen"] = str(candidate.get("label", guarded))
            updated["selectedAction"] = {
                "arrayIndex": 0,
                "optionIndex": guarded_index,
                "kind": candidate.get("kind"),
                "cardId": candidate.get("cardId"),
                "serial": None,
                "effectSource": "OfficialSearchCycleGuard",
                "label": candidate.get("label"),
            }
        tree = updated.get("searchTree")
        if isinstance(tree, dict) and isinstance(tree.get("children"), list):
            children = []
            for index, child in enumerate(tree["children"]):
                node = dict(child) if isinstance(child, dict) else child
                if isinstance(node, dict):
                    if index == guarded_index:
                        node["status"] = "selected"
                        node["selected"] = True
                    elif index in blocked:
                        node["status"] = "pruned"
                        node["selected"] = False
                        node["pruned"] = True
                    elif node.get("status") == "selected":
                        node["status"] = "expanded"
                        node["selected"] = False
                children.append(node)
            tree = dict(tree)
            tree["children"] = children
            updated["searchTree"] = tree
        warnings = list(updated.get("warnings") or [])
        warnings.append(f"OfficialSearchCycleGuard changed selection {list(selection)} -> {guarded}")
        updated["warnings"] = warnings
        ledger = dict(updated.get("truthLedger") or {})
        ledger.update({
            "searchGuard": "APPLIED",
            "searchGuardBlocked": sorted(blocked),
            "searchGuardOriginalSelection": list(selection),
            "searchGuardFinalSelection": guarded,
        })
        updated["truthLedger"] = ledger
        self._last_overlay = updated
        return guarded


DECK = read_deck(ROOT / "deck.csv")
POLICY = SearchGuardedDragapultPolicy()
RUNTIME = SubmissionRuntime(
    POLICY,
    DECK,
    budget_ms=float(os.environ.get("BLACK_AGENT_BUDGET_MS", "500")),
)


def agent(obs, configuration=None):
    return RUNTIME.agent(obs, configuration)


def get_black_decision_overlay():
    """Local Battle Studio side-channel; ignored by Kaggle submission runtime."""
    return RUNTIME.get_decision_overlay()

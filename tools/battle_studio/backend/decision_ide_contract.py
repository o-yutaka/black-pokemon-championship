from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    value = _number(value)
    return int(value) if value is not None and value.is_integer() else None


def _ratio(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return min(1.0, max(0.0, number))


def _primitive_record(value: Any) -> dict[str, str | int | float | bool | None]:
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in _mapping(value).items():
        if item is None or isinstance(item, (str, int, float, bool)):
            result[str(key)] = item
    return result


def _number_record(value: Any, ratios: bool = False) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, item in _mapping(value).items():
        number = _ratio(item) if ratios else _number(item)
        if number is not None:
            result[str(key)] = number
    return result


def _search_node(value: Any, fallback_id: str, depth: int = 0) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or depth > 7:
        return None
    node = dict(value)
    label = str(node.get("label", node.get("action", node.get("name", fallback_id))))
    status = str(node.get("status", "available")).lower()
    if status not in {"root", "available", "expanded", "selected", "pruned"}:
        status = "available"
    children: list[dict[str, Any]] = []
    for index, child in enumerate(_sequence(node.get("children", node.get("branches", [])))):
        normalized = _search_node(child, f"{fallback_id}.{index}", depth + 1)
        if normalized:
            children.append(normalized)
    return {
        "id": str(node.get("id", fallback_id)),
        "label": label,
        "status": status,
        "ev": _number(node.get("ev", node.get("score"))),
        "visits": _integer(node.get("visits")),
        "mean": _number(node.get("mean")),
        "worst": _number(node.get("worst")),
        "best": _number(node.get("best")),
        "reason": None if node.get("reason") in (None, "") else str(node.get("reason")),
        "children": children,
    }


def _inferred_search_tree(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    children = []
    for index, candidate in enumerate(candidates):
        selected = bool(candidate.get("selected"))
        reason = candidate.get("reason")
        children.append({
            "id": f"option-{index}",
            "label": str(candidate.get("label", f"選択肢 {index}")),
            "status": "selected" if selected else ("pruned" if reason else "available"),
            "ev": _number(candidate.get("score")),
            "visits": None,
            "mean": None,
            "worst": None,
            "best": None,
            "reason": None if reason in (None, "") else str(reason),
            "children": [],
        })
    return {
        "id": "root",
        "label": "Root（公式候補から推定）",
        "status": "root",
        "ev": None,
        "visits": None,
        "mean": None,
        "worst": None,
        "best": None,
        "reason": "Agentが探索統計を提供していないため、候補一覧のみ表示",
        "children": children,
    }


def _rejected_branches(value: Any, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(_sequence(value)):
        if not isinstance(item, Mapping):
            continue
        branch = dict(item)
        result.append({
            "label": str(branch.get("label", branch.get("action", branch.get("name", f"Rejected {index}")))),
            "reason": str(branch.get("reason", "理由未提供")),
            "evidence": [str(entry) for entry in _sequence(branch.get("evidence"))],
            "metrics": _primitive_record(branch.get("metrics")),
            "killedBy": [str(entry) for entry in _sequence(branch.get("killedBy", branch.get("killed_by", [])))],
        })
    if result:
        return result
    for candidate in candidates:
        if candidate.get("selected") or not candidate.get("reason"):
            continue
        result.append({
            "label": str(candidate.get("label", "Rejected")),
            "reason": str(candidate["reason"]),
            "evidence": [],
            "metrics": {"score": float(candidate.get("score", 0.0))},
            "killedBy": [],
        })
    return result


def _policy_trace(value: Any) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(_sequence(value)):
        if not isinstance(item, Mapping):
            continue
        entry = dict(item)
        status = str(entry.get("status", "SKIP")).upper()
        if status not in {"PASS", "FAIL", "HOLD", "SKIP"}:
            status = "SKIP"
        result.append({
            "name": str(entry.get("name", entry.get("policy", f"Policy {index}"))),
            "status": status,
            "score": _number(entry.get("score")) or 0.0,
            "reason": str(entry.get("reason", "")),
        })
    return result


def _route(value: Any) -> dict[str, Any] | None:
    route = _mapping(value)
    if not route:
        return None
    steps = [str(item) for item in _sequence(route.get("steps"))]
    current = _integer(route.get("currentStep", route.get("current", 0))) or 0
    return {"name": str(route.get("name", "Win Route")), "steps": steps, "currentStep": max(0, current)}


def _prize_planner(value: Any) -> dict[str, Any] | None:
    planner = _mapping(value)
    if not planner:
        return None
    alternatives = []
    for index, item in enumerate(_sequence(planner.get("alternatives"))):
        if not isinstance(item, Mapping):
            continue
        alternatives.append({
            "label": str(item.get("label", item.get("name", f"Route {index}"))),
            "score": _number(item.get("score")) or 0.0,
            "selected": bool(item.get("selected", False)),
        })
    return {
        "neededAttacks": _number(planner.get("neededAttacks", planner.get("needed"))),
        "expectedAttacks": _number(planner.get("expectedAttacks", planner.get("expected"))),
        "risk": _ratio(planner.get("risk")),
        "alternatives": alternatives,
    }


def _board_analysis(value: Any) -> dict[str, Any] | None:
    analysis = _mapping(value)
    if not analysis:
        return None
    return {
        "total": _number(analysis.get("total", analysis.get("boardValue"))),
        "components": _number_record(analysis.get("components", analysis.get("values"))),
        "threatMap": _number_record(analysis.get("threatMap", analysis.get("threats"))),
    }


def _counterfactuals(value: Any) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(_sequence(value)):
        if not isinstance(item, Mapping):
            continue
        entry = dict(item)
        result.append({
            "label": str(entry.get("label", entry.get("action", f"Alternative {index}"))),
            "baselineWinRate": _ratio(entry.get("baselineWinRate", entry.get("currentWinRate"))),
            "alternativeWinRate": _ratio(entry.get("alternativeWinRate", entry.get("winRate"))),
            "reason": str(entry.get("reason", "")),
        })
    return result


def _causality(value: Any) -> dict[str, Any] | None:
    graph = _mapping(value)
    if not graph:
        return None
    edges = []
    for item in _sequence(graph.get("edges")):
        if not isinstance(item, Mapping) or item.get("from") is None or item.get("to") is None:
            continue
        edge = {"from": str(item["from"]), "to": str(item["to"])}
        if item.get("label") is not None:
            edge["label"] = str(item["label"])
        edges.append(edge)
    return {"nodes": [str(item) for item in _sequence(graph.get("nodes"))], "edges": edges}


def normalize_ide_fields(overlay: Mapping[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    search_tree = _search_node(overlay.get("searchTree"), "root") or _inferred_search_tree(candidates)
    decision_diff = _mapping(overlay.get("decisionDiff"))
    result: dict[str, Any] = {
        "priority": [str(item) for item in _sequence(overlay.get("priority", overlay.get("priorities", [])))],
        "expectedWinRate": _ratio(overlay.get("expectedWinRate", overlay.get("expectedWR", overlay.get("winRate")))),
        "searchTree": search_tree,
        "rejectedBranches": _rejected_branches(overlay.get("rejectedBranches", overlay.get("rejected", [])), candidates),
        "policyTrace": _policy_trace(overlay.get("policyTrace", overlay.get("policies", []))),
        "boardAnalysis": _board_analysis(overlay.get("boardAnalysis")),
        "route": _route(overlay.get("route", overlay.get("winRoute"))),
        "prizePlanner": _prize_planner(overlay.get("prizePlanner")),
        "heatmap": _number_record(overlay.get("heatmap")),
        "policyBattle": _number_record(overlay.get("policyBattle")),
        "counterfactuals": _counterfactuals(overlay.get("counterfactuals", overlay.get("counterfactual", []))),
        "causalityGraph": _causality(overlay.get("causalityGraph", overlay.get("causality"))),
        "hiddenBelief": _number_record(overlay.get("hiddenBelief", overlay.get("belief")), ratios=True),
        "truthLedger": _primitive_record(overlay.get("truthLedger")),
    }
    if overlay.get("decisionId") is not None:
        result["decisionId"] = str(overlay["decisionId"])
    if decision_diff:
        result["decisionDiff"] = {
            "previous": str(decision_diff.get("previous", "")),
            "current": str(decision_diff.get("current", "")),
            "why": str(decision_diff.get("why", "")),
            "delta": _number(decision_diff.get("delta")),
        }
    return result

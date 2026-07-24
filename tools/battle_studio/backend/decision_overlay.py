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
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item, depth + 1) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_safe(item, depth + 1) for item in value]
    return str(value)


def split_agent_result(result: Any) -> tuple[Any, dict[str, Any] | None]:
    if not isinstance(result, Mapping) or "selection" not in result:
        return result, None
    overlay = result.get("overlay", result.get("decisionOverlay", result.get("decision")))
    return result.get("selection"), _mapping(overlay) or None


def _nested_values(option: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values: list[Mapping[str, Any]] = [option]
    for key in ("card", "source", "target", "action", "effect", "option"):
        nested = option.get(key)
        if isinstance(nested, Mapping):
            values.append(nested)
    return values


def _first(option: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for source in _nested_values(option):
        for key in keys:
            if source.get(key) is not None:
                return source[key]
    return None


def _option_label(index: int, option: Any) -> str:
    if not isinstance(option, Mapping):
        return f"選択肢 {index}: {option}"
    kind = _first(option, ("kind", "actionType", "type", "selectType", "category", "command"))
    source = _first(option, ("effectSource", "sourceName", "cardName", "name", "label"))
    card_id = _integer(_first(option, ("cardId", "card_id", "id")))
    serial = _integer(_first(option, ("serial", "instanceSerial", "cardSerial")))
    parts = [f"[{index}]", str(kind) if kind is not None else "ACTION"]
    if source not in (None, ""):
        parts.append(str(source))
    if card_id is not None:
        parts.append(f"#{card_id}")
    if serial is not None:
        parts.append(f"serial={serial}")
    return " · ".join(parts)


def _selected_action(index: int, array_index: int, option: Any) -> dict[str, Any]:
    source = option if isinstance(option, Mapping) else {}
    return {
        "arrayIndex": _integer(_first(source, ("arrayIndex", "array_index"))) if source else array_index,
        "optionIndex": index,
        "kind": str(_first(source, ("kind", "actionType", "type", "selectType", "category", "command")) or "UNKNOWN"),
        "cardId": _integer(_first(source, ("cardId", "card_id", "id"))),
        "serial": _integer(_first(source, ("serial", "instanceSerial", "cardSerial"))),
        "effectSource": str(_first(source, ("effectSource", "sourceName", "cardName", "name", "label")) or ""),
        "label": _option_label(index, option),
    }


def infer_selected_actions(observation: Mapping[str, Any], selection: Sequence[int]) -> list[dict[str, Any]]:
    select = _mapping(observation.get("select"))
    options = _sequence(select.get("option", select.get("options", [])))
    actions: list[dict[str, Any]] = []
    for array_index, index in enumerate(selection):
        option = options[index] if isinstance(index, int) and 0 <= index < len(options) else None
        actions.append(_selected_action(int(index), array_index, option))
    return actions


def infer_candidates(observation: Mapping[str, Any], selection: Sequence[int], limit: int = 32) -> list[dict[str, Any]]:
    select = _mapping(observation.get("select"))
    options = _sequence(select.get("option", select.get("options", [])))
    selected = set(selection)
    return [
        {"label": _option_label(index, option), "score": 1.0 if index in selected else 0.0, "selected": index in selected}
        for index, option in enumerate(options[:limit])
    ]


def _normalize_candidates(value: Any, selection_labels: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(_sequence(value)):
        if isinstance(item, Mapping):
            label = str(item.get("label", item.get("action", item.get("name", f"候補 {index}"))))
            score = _number(item.get("score", item.get("total", 0.0))) or 0.0
            selected = bool(item.get("selected", label in selection_labels))
            normalized = {"label": label, "score": score, "selected": selected}
            for key in ("reason", "kind"):
                if item.get(key) is not None:
                    normalized[key] = str(item[key])
            for key in ("cardId", "serial"):
                number = _integer(item.get(key))
                if number is not None:
                    normalized[key] = number
            result.append(normalized)
        else:
            label = str(item)
            result.append({"label": label, "score": 0.0, "selected": label in selection_labels})
    return result


def normalize_decision_overlay(
    observation: Mapping[str, Any],
    selection: Sequence[int],
    elapsed_ms: float,
    error: str | None,
    explicit_overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    overlay = _mapping(explicit_overlay)
    inferred_actions = infer_selected_actions(observation, selection)
    explicit_action = _mapping(overlay.get("selectedAction"))
    selected_action = {**(inferred_actions[0] if inferred_actions else {}), **explicit_action} if (inferred_actions or explicit_action) else None

    selected_actions = _sequence(overlay.get("selectedActions"))
    if not selected_actions:
        selected_actions = inferred_actions
    selected_actions = [json_safe(item) for item in selected_actions if isinstance(item, Mapping)]

    chosen = str(overlay.get("chosen") or (selected_action or {}).get("label") or list(selection))
    selection_labels = {chosen, *(str(item.get("label")) for item in selected_actions if isinstance(item, Mapping) and item.get("label"))}
    explicit_candidates = overlay.get("candidates", overlay.get("alternatives"))
    candidates = _normalize_candidates(explicit_candidates, selection_labels) if explicit_candidates is not None else infer_candidates(observation, selection)

    scores = {str(key): number for key, value in _mapping(overlay.get("scores")).items() if (number := _number(value)) is not None}
    flags = {str(key): bool(value) for key, value in _mapping(overlay.get("flags")).items()}
    kind = str((selected_action or {}).get("kind", "")).upper()
    if "abilityUsed" not in flags and kind:
        flags["abilityUsed"] = "ABILITY" in kind

    warnings = [str(item) for item in _sequence(overlay.get("warnings"))]
    if error:
        warnings.append(error)

    confidence = _number(overlay.get("confidence"))
    if confidence is not None:
        confidence = min(1.0, max(0.0, confidence))

    score_source = str(overlay.get("scoreSource") or ("agent" if explicit_candidates is not None or scores else "official_options_only"))
    return {
        "overlayVersion": str(overlay.get("schemaVersion", overlay.get("overlayVersion", "1.0"))),
        "goal": str(overlay.get("goal", "uploaded_bundle_agent")),
        "chosen": chosen,
        "confidence": confidence,
        "elapsedMs": max(0.0, float(elapsed_ms)),
        "candidates": candidates,
        "selectedAction": json_safe(selected_action),
        "selectedActions": selected_actions,
        "scores": scores,
        "flags": flags,
        "warnings": warnings,
        "alternatives": _normalize_candidates(overlay.get("alternatives", []), selection_labels),
        "boardDiff": [str(item) for item in _sequence(overlay.get("boardDiff"))],
        "scoreSource": score_source,
    }


def _card_signature(card: Any) -> tuple[Any, ...] | None:
    if not isinstance(card, Mapping):
        return None
    return (
        card.get("cardId"), card.get("serial"), card.get("damage"), tuple(_sequence(card.get("energies"))),
        tuple(_sequence(card.get("tools"))), tuple(_sequence(card.get("status"))), tuple(_sequence(card.get("evolution"))),
    )


def build_board_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    changes: list[str] = []
    before_players = _sequence(before.get("players"))
    after_players = _sequence(after.get("players"))
    for player_index in range(min(2, len(before_players), len(after_players))):
        previous = _mapping(before_players[player_index])
        current = _mapping(after_players[player_index])
        player_label = f"P{player_index + 1}"
        for key, label in (("handCount", "手札"), ("deckCount", "山札"), ("prizeCount", "サイド")):
            old = _integer(previous.get(key))
            new = _integer(current.get(key))
            if old is not None and new is not None and old != new:
                changes.append(f"{player_label} {label}: {old}→{new} ({new - old:+d})")
        old_discard = len(_sequence(previous.get("discard")))
        new_discard = len(_sequence(current.get("discard")))
        if old_discard != new_discard:
            changes.append(f"{player_label} トラッシュ: {old_discard}→{new_discard} ({new_discard - old_discard:+d})")
        if _card_signature(previous.get("active")) != _card_signature(current.get("active")):
            changes.append(f"{player_label} バトル場が変化")
        previous_bench = [_card_signature(item) for item in _sequence(previous.get("bench"))]
        current_bench = [_card_signature(item) for item in _sequence(current.get("bench"))]
        if previous_bench != current_bench:
            changes.append(f"{player_label} ベンチが変化")
    if before.get("turn") != after.get("turn"):
        changes.append(f"ターン: {before.get('turn')}→{after.get('turn')}")
    if before.get("actingPlayer") != after.get("actingPlayer"):
        changes.append(f"行動プレイヤー: P{int(before.get('actingPlayer', 0)) + 1}→P{int(after.get('actingPlayer', 0)) + 1}")
    return changes[:40]

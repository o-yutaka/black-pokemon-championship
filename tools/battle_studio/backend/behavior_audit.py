from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Finding:
    code: str
    category: str
    severity: str
    frame: int
    player: int
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _seq(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _cards(player: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    active = player.get("active")
    if isinstance(active, Mapping):
        out.append(active)
    out.extend(item for item in _seq(player.get("bench")) if isinstance(item, Mapping))
    return out


def _serial(card: Mapping[str, Any]) -> int | str | None:
    return card.get("serial") or card.get("instanceId") or card.get("cardId") or card.get("id")


def _energy_count(card: Mapping[str, Any]) -> int:
    return len(_seq(card.get("energies")))


def _event_types(frame: Mapping[str, Any], player: int) -> Counter[str]:
    return Counter(
        str(event.get("type", "")).lower()
        for event in _seq(frame.get("events"))
        if isinstance(event, Mapping) and event.get("actor") in (player, None)
    )


def _attack_available(frame: Mapping[str, Any]) -> bool:
    decision = _mapping(frame.get("decision"))
    candidates = _seq(decision.get("candidates"))
    return any(isinstance(item, Mapping) and str(item.get("kind", "")).lower() == "attack" for item in candidates)


def _selected_kind(frame: Mapping[str, Any]) -> str | None:
    decision = _mapping(frame.get("decision"))
    for item in _seq(decision.get("candidates")):
        if isinstance(item, Mapping) and item.get("selected"):
            return str(item.get("kind", "")).lower() or None
    return None


def audit_frames(frames: Iterable[Mapping[str, Any]], subject_player: int = 0) -> dict[str, Any]:
    items = [dict(frame) for frame in frames if isinstance(frame, Mapping)]
    findings: list[Finding] = []
    switches: list[tuple[int, Any, Any]] = []

    for index in range(1, len(items)):
        before, after = items[index - 1], items[index]
        before_players = _seq(before.get("players"))
        after_players = _seq(after.get("players"))
        if len(before_players) <= subject_player or len(after_players) <= subject_player:
            continue
        bp = _mapping(before_players[subject_player])
        ap = _mapping(after_players[subject_player])
        b_active = _mapping(bp.get("active"))
        a_active = _mapping(ap.get("active"))
        b_serial, a_serial = _serial(b_active), _serial(a_active)
        events = _event_types(after, subject_player)

        if b_serial != a_serial and b_serial is not None and a_serial is not None:
            switches.append((index, b_serial, a_serial))
            if events["switch"] + events["retreat"] == 0:
                findings.append(Finding("SWITCH_UNEXPLAINED", "switch", "medium", index, subject_player, {"from": b_serial, "to": a_serial}))

        if len(switches) >= 2:
            i1, from1, to1 = switches[-2]
            i2, from2, to2 = switches[-1]
            if i2 - i1 <= 3 and from1 == to2 and to1 == from2:
                findings.append(Finding("SWITCH_BACKTRACK_LOOP", "switch", "high", index, subject_player, {"first": i1, "second": i2, "route": [from1, to1, to2]}))

        before_energy = {_serial(card): _energy_count(card) for card in _cards(bp)}
        after_energy = {_serial(card): _energy_count(card) for card in _cards(ap)}
        for key, count in after_energy.items():
            delta = count - before_energy.get(key, 0)
            if delta <= 0:
                continue
            target = next((card for card in _cards(ap) if _serial(card) == key), {})
            if key == a_serial and _attack_available(before) and _selected_kind(before) not in {"attack", "ability"}:
                findings.append(Finding("ACTIVE_ATTACH_WITH_ATTACK_WINDOW", "energy", "medium", index, subject_player, {"target": key, "delta": delta}))
            if target and target.get("zone") == "bench" and _energy_count(target) >= 3:
                findings.append(Finding("BENCH_ENERGY_OVERCOMMIT", "energy", "medium", index, subject_player, {"target": key, "energy": _energy_count(target)}))

        if _attack_available(before):
            selected = _selected_kind(before)
            if selected not in {None, "attack", "ability"}:
                findings.append(Finding("ATTACK_WINDOW_SKIPPED", "tempo", "high", index - 1, subject_player, {"selectedKind": selected}))

        if events["ability"] == 0:
            decision = _mapping(before.get("decision"))
            ability_candidates = [item for item in _seq(decision.get("candidates")) if isinstance(item, Mapping) and str(item.get("kind", "")).lower() == "ability"]
            selected = _selected_kind(before)
            if ability_candidates and selected not in {"ability", "attack"}:
                findings.append(Finding("ABILITY_WINDOW_SKIPPED", "ability", "medium", index - 1, subject_player, {"selectedKind": selected, "abilityCount": len(ability_candidates)}))

        if events["retreat"] and events["switch"]:
            findings.append(Finding("RETREAT_AND_SWITCH_SAME_STEP", "switch", "high", index, subject_player, {}))

        if bp.get("supporterPlayed") and not ap.get("supporterPlayed") and before.get("turn") == after.get("turn"):
            findings.append(Finding("SUPPORTER_STATE_REGRESSION", "resource", "medium", index, subject_player, {}))

    category_counts = Counter(item.category for item in findings)
    severity_counts = Counter(item.severity for item in findings)
    return {
        "schemaVersion": "BLACK_BEHAVIOR_AUDIT_V1",
        "frames": len(items),
        "subjectPlayer": subject_player,
        "findingCount": len(findings),
        "categoryCounts": dict(category_counts),
        "severityCounts": dict(severity_counts),
        "findings": [item.as_dict() for item in findings],
        "gate": "PASS" if not severity_counts.get("high") else "HOLD",
    }

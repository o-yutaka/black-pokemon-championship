#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from behavior_audit import audit_frames

_ACTION_KIND = {
    7: "trainer",
    8: "ability",
    9: "evolve",
    10: "switch",
    12: "retreat",
    13: "attack",
    14: "pass",
}


def _selected_positions(action: Any) -> set[int]:
    if isinstance(action, list):
        return {item for item in action if type(item) is int and item >= 0}
    return set()


def _cabt_frames(value: Mapping[str, Any], subject_player: int) -> list[Mapping[str, Any]]:
    steps = value.get("steps")
    if not isinstance(steps, list):
        return []
    frames: list[Mapping[str, Any]] = []
    for step_index, step in enumerate(steps):
        if not isinstance(step, list) or len(step) <= subject_player:
            continue
        record = step[subject_player]
        if not isinstance(record, Mapping):
            continue
        observation = record.get("observation")
        if not isinstance(observation, Mapping):
            continue
        current = observation.get("current")
        if not isinstance(current, Mapping):
            continue
        select = observation.get("select")
        options = select.get("option", []) if isinstance(select, Mapping) else []
        selected = _selected_positions(record.get("action"))
        candidates = []
        for position, option in enumerate(options if isinstance(options, list) else []):
            if not isinstance(option, Mapping):
                continue
            raw_type = option.get("type")
            kind = _ACTION_KIND.get(raw_type, "other") if isinstance(raw_type, int) else str(raw_type or "other").lower()
            candidates.append({
                "kind": kind,
                "selected": position in selected,
                "position": position,
                "option": dict(option),
            })
        frame = dict(current)
        frame["stepIndex"] = step_index
        frame["players"] = current.get("players", [])
        frame["events"] = current.get("logs", observation.get("logs", []))
        frame["decision"] = {
            "candidates": candidates,
            "selectedPositions": sorted(selected),
            "context": select.get("context") if isinstance(select, Mapping) else None,
        }
        frames.append(frame)
    return frames


def _frames(value: Any, subject_player: int) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []
    cabt = _cabt_frames(value, subject_player)
    if cabt:
        return cabt
    for key in ("frames", "replay", "snapshots"):
        nested = value.get(key)
        if isinstance(nested, list):
            if any(not isinstance(item, Mapping) for item in nested):
                raise ValueError(f"壊れた明示的{key}配列です")
            return list(nested)
    for key in ("output", "result", "payload", "data"):
        found = _frames(value.get(key), subject_player)
        if found:
            return found
    if isinstance(value.get("frame"), Mapping):
        return [value["frame"]]
    return []


def load_frames(path: Path, subject_player: int = 0) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        value = json.loads(text)
        frames = _frames(value, subject_player)
        if frames:
            return frames
    except json.JSONDecodeError:
        pass
    frames: list[Mapping[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        frames.extend(_frames(value, subject_player))
    if not frames:
        raise ValueError("監査可能なframesが見つかりません")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    parser.add_argument("--subject-player", type=int, choices=(0, 1), default=0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit_frames(load_frames(args.replay, args.subject_player), args.subject_player)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["gate"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

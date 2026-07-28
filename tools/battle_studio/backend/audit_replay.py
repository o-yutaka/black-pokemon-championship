#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from behavior_audit import audit_frames


def _frames(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []
    for key in ("frames", "replay", "snapshots"):
        nested = value.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, Mapping)]
    for key in ("output", "result", "payload", "data"):
        nested = value.get(key)
        found = _frames(nested)
        if found:
            return found
    if isinstance(value.get("frame"), Mapping):
        return [value["frame"]]
    return []


def load_frames(path: Path) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        value = json.loads(text)
        frames = _frames(value)
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
        frames.extend(_frames(value))
    if not frames:
        raise ValueError("監査可能なframesが見つかりません")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    parser.add_argument("--subject-player", type=int, choices=(0, 1), default=0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit_frames(load_frames(args.replay), args.subject_player)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["gate"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

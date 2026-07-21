from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_deck(path: Path) -> list[int]:
    values: list[int] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if row and str(row[0]).strip().isdigit():
                values.append(int(row[0]))
    if len(values) != 60:
        raise ValueError(f"{path}: expected 60 cards, got {len(values)}")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-backed Bayesian archetype template bank.")
    parser.add_argument("--template", action="append", default=[], metavar="NAME=DECK_CSV")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    templates = []
    for value in args.template:
        if "=" not in value:
            raise SystemExit(f"invalid --template {value!r}; expected NAME=DECK_CSV")
        name, raw_path = value.split("=", 1)
        deck_path = Path(raw_path)
        templates.append({
            "name": name.strip(),
            "deck": read_deck(deck_path),
            "prior": 1.0,
            "source": str(deck_path.resolve()),
        })
    payload = {
        "version": 1,
        "status": "EVIDENCE_BACKED" if templates else "EMPTY_REQUIRES_EVIDENCE_BACKED_TEMPLATES",
        "templates": templates,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"templates": len(templates), "output": str(output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

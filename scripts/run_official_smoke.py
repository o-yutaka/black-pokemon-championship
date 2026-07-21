from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_lab import read_deck
from engine.official_runtime import run_battle


def load_candidate(name: str):
    directory = ROOT / "candidates" / name
    path = directory / "main.py"
    spec = importlib.util.spec_from_file_location(f"candidate_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load candidate: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    deck = read_deck(directory / "deck.csv")
    if len(deck) != 60:
        raise RuntimeError(f"{name}: deck size={len(deck)}")
    if module.agent(None, None) != deck:
        raise RuntimeError(f"{name}: deck handshake mismatch")
    return deck, module.agent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cg-dir", default="/home/user/HROS/submission/cg")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "official_smoke.json"))
    args = parser.parse_args()
    if args.games <= 0:
        raise SystemExit("--games must be positive")

    mewtwo = load_candidate("mewtwo_spidops")
    garchomp = load_candidate("garchomp_spiritomb")
    output = Path(args.out)
    trace_dir = output.parent / (output.stem + "_traces")
    output.parent.mkdir(parents=True, exist_ok=True)

    wins = {"mewtwo_spidops": 0, "garchomp_spiritomb": 0}
    errors = 0
    games: list[dict] = []
    provenance = None

    for index in range(args.games):
        reversed_seats = index % 2 == 1
        if not reversed_seats:
            deck0, agent0, name0 = *mewtwo, "mewtwo_spidops"
            deck1, agent1, name1 = *garchomp, "garchomp_spiritomb"
        else:
            deck0, agent0, name0 = *garchomp, "garchomp_spiritomb"
            deck1, agent1, name1 = *mewtwo, "mewtwo_spidops"

        report = run_battle(
            deck0,
            agent0,
            deck1,
            agent1,
            cg_dir=args.cg_dir,
            max_steps=args.max_steps,
            trace_path=trace_dir / f"game_{index:04d}.jsonl",
        )
        provenance = provenance or report.get("provenance")
        winner = None
        if report["completed"] and report["result"] in (0, 1):
            winner = name0 if report["result"] == 0 else name1
            wins[winner] += 1
        else:
            errors += 1
        games.append(
            {
                "game": index,
                "seat0": name0,
                "seat1": name1,
                "winner": winner,
                **report,
            }
        )

    summary = {
        "verdict": "OFFICIAL_SMOKE_PASS" if errors == 0 else "OFFICIAL_SMOKE_FAIL",
        "games_requested": args.games,
        "games_completed": args.games - errors,
        "errors": errors,
        "wins": wins,
        "seat_policy": "alternating",
        "seed_control": "UNAVAILABLE_IN_OFFICIAL_BATTLE_START",
        "provenance": provenance,
        "records": games,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, ensure_ascii=False, indent=2))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine import DragapultPolicy, read_deck
from black_engine.runtime import deterministic_fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, required=True)
    parser.add_argument("--cg-dir", required=True)
    parser.add_argument("--opponent-deck", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cg_dir = Path(args.cg_dir).resolve(); sys.path.insert(0, str(cg_dir.parent))
    game = importlib.import_module("cg.game")
    deck, opponent = read_deck(ROOT / "deck.csv"), read_deck(args.opponent_deck)
    policy = DragapultPolicy(); policy.set_deck(deck)
    wins = errors = 0
    for _ in range(args.games):
        try:
            obs, _ = game.battle_start(deck, opponent)
            steps = 0
            while isinstance(obs, dict) and (obs.get("current") or {}).get("result", -1) not in (0, 1) and steps < 20000:
                actor = (obs.get("current") or {}).get("yourIndex", 0)
                action = policy.agent(obs, None) if actor == 0 else deterministic_fallback(obs)
                obs = game.battle_select(action); steps += 1
            result = (obs.get("current") or {}).get("result", -1) if isinstance(obs, dict) else -1
            wins += int(result == 0); errors += int(result not in (0, 1))
        except Exception:
            errors += 1
        finally:
            try: game.battle_finish()
            except Exception: errors += 1
    Path(args.out).write_text(json.dumps({"games": args.games, "wins": wins, "errors": errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

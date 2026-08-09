from __future__ import annotations

import argparse
import importlib
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine import DragapultPolicy, SubmissionRuntime, read_deck
from black_engine.runtime import deterministic_fallback


def _worker(args: tuple[int, int, str, str, int, float]) -> dict:
    worker_id, games, cg_dir, opponent_deck_path, max_steps, budget_ms = args
    os.environ.update({
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    })

    cg_dir = str(Path(cg_dir).resolve())
    sys.path.insert(0, str(Path(cg_dir).parent))
    game = importlib.import_module("cg.game")

    deck = read_deck(ROOT / "deck.csv")
    opponent = read_deck(opponent_deck_path)
    runtime = SubmissionRuntime(DragapultPolicy(), deck, budget_ms=budget_ms)

    wins = losses = errors = steps_total = fallbacks = 0
    started = time.perf_counter()
    for _ in range(games):
        try:
            obs, _ = game.battle_start(deck, opponent)
            steps = 0
            while isinstance(obs, dict) and (obs.get("current") or {}).get("result", -1) not in (0, 1):
                if steps >= max_steps:
                    errors += 1
                    break
                actor = (obs.get("current") or {}).get("yourIndex", 0)
                if actor == 0:
                    decision = runtime.decide(obs, None)
                    action = decision.selection
                    fallbacks += int(decision.source == "fallback")
                else:
                    action = deterministic_fallback(obs)
                obs = game.battle_select(action)
                steps += 1
            else:
                result = (obs.get("current") or {}).get("result", -1) if isinstance(obs, dict) else -1
                wins += int(result == 0)
                losses += int(result == 1)
                errors += int(result not in (0, 1))
                steps_total += steps
        except Exception:
            errors += 1
        finally:
            try:
                game.battle_finish()
            except Exception:
                errors += 1

    elapsed = time.perf_counter() - started
    return {
        "worker": worker_id,
        "games": games,
        "wins": wins,
        "losses": losses,
        "errors": errors,
        "fallbacks": fallbacks,
        "steps": steps_total,
        "elapsed_seconds": round(elapsed, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lightweight PC multi-process CABT simulator.")
    parser.add_argument("--cg-dir", required=True, help="Path containing the official cg package.")
    parser.add_argument("--opponent-deck", required=True)
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 2)))
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--budget-ms", type=float, default=500.0)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "pc_simulation" / "summary.json"))
    args = parser.parse_args()

    if args.games <= 0 or args.workers <= 0 or args.max_steps <= 0:
        raise SystemExit("games/workers/max-steps must be positive")

    workers = min(args.workers, args.games)
    base, remainder = divmod(args.games, workers)
    jobs = [
        (i, base + int(i < remainder), args.cg_dir, args.opponent_deck, args.max_steps, args.budget_ms)
        for i in range(workers)
        if base + int(i < remainder) > 0
    ]

    started = time.perf_counter()
    results: list[dict] = []
    with mp.get_context("spawn").Pool(len(jobs)) as pool:
        for row in pool.imap_unordered(_worker, jobs):
            results.append(row)
            done = sum(r["games"] for r in results)
            wins = sum(r["wins"] for r in results)
            errors = sum(r["errors"] for r in results)
            decided = max(1, done - errors)
            print(f"[{done}/{args.games}] WR={wins / decided:.2%} errors={errors}", flush=True)

    elapsed = time.perf_counter() - started
    games = sum(r["games"] for r in results)
    wins = sum(r["wins"] for r in results)
    losses = sum(r["losses"] for r in results)
    errors = sum(r["errors"] for r in results)
    fallbacks = sum(r["fallbacks"] for r in results)
    decided = wins + losses

    summary = {
        "mode": "pc_lightweight_official_engine",
        "games": games,
        "wins": wins,
        "losses": losses,
        "errors": errors,
        "fallbacks": fallbacks,
        "win_rate": wins / decided if decided else 0.0,
        "workers": workers,
        "elapsed_seconds": round(elapsed, 3),
        "games_per_second": round(games / max(elapsed, 0.001), 2),
        "avg_steps_per_decided_game": round(sum(r["steps"] for r in results) / max(decided, 1), 2),
        "worker_results": sorted(results, key=lambda r: r["worker"]),
        "official_evidence": False,
    }

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "worker_results"}, indent=2))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

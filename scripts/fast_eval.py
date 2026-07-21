from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _worker(args: tuple[int, int, str, str, str]) -> dict:
    worker_id, games, cg_dir, opponent_deck, output_dir = args
    env = os.environ.copy()
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
    cmd = [sys.executable, str(ROOT / "scripts" / "worker_eval.py"), "--games", str(games), "--cg-dir", cg_dir, "--opponent-deck", opponent_deck, "--out", str(Path(output_dir) / f"worker_{worker_id:02d}.json")]
    started = time.time()
    process = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if process.returncode != 0:
        return {"worker": worker_id, "games": games, "errors": games, "stderr": process.stderr[-2000:]}
    payload = json.loads((Path(output_dir) / f"worker_{worker_id:02d}.json").read_text())
    payload["worker"] = worker_id
    payload["wall_seconds"] = round(time.time() - started, 3)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel official-engine crash/speed screen.")
    parser.add_argument("--cg-dir", required=True)
    parser.add_argument("--opponent-deck", required=True)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--out-dir", default=str(ROOT / "artifacts" / "fast_eval"))
    args = parser.parse_args()
    if args.games <= 0 or args.workers <= 0:
        raise SystemExit("games/workers must be positive")
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    base, remainder = divmod(args.games, args.workers)
    jobs = [(index, base + int(index < remainder), args.cg_dir, args.opponent_deck, str(out)) for index in range(args.workers) if base + int(index < remainder) > 0]
    started = time.time(); results = []
    with mp.get_context("spawn").Pool(len(jobs)) as pool:
        for row in pool.imap_unordered(_worker, jobs):
            results.append(row)
            done = sum(int(value.get("games", 0)) for value in results)
            wins = sum(int(value.get("wins", 0)) for value in results)
            errors = sum(int(value.get("errors", 0)) for value in results)
            decided = max(1, done - errors)
            print(f"[{done}/{args.games}] WR={wins/decided:.3%} wins={wins} errors={errors}", flush=True)
    games = sum(int(row.get("games", 0)) for row in results)
    wins = sum(int(row.get("wins", 0)) for row in results)
    errors = sum(int(row.get("errors", 0)) for row in results)
    decided = games - errors
    elapsed = time.time() - started
    summary = {"verdict": "PASS" if errors == 0 else "FAIL", "games": games, "wins": wins, "losses": max(0, decided - wins), "errors": errors, "win_rate": wins / decided if decided else 0.0, "workers": len(jobs), "elapsed_seconds": round(elapsed, 3), "games_per_second": round(games / max(0.001, elapsed), 3), "worker_results": sorted(results, key=lambda row: row.get("worker", 0))}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    with (out / "summary.csv").open("w", newline="") as handle:
        fields = ["games", "wins", "losses", "errors", "win_rate", "workers", "elapsed_seconds", "games_per_second"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerow({key: summary[key] for key in fields})
    (out / "SUMMARY.md").write_text(f"# Fast Eval\n\n- Verdict: **{summary['verdict']}**\n- Games: **{games}**\n- Win rate: **{summary['win_rate']:.2%}**\n- Errors: **{errors}**\n- Workers: **{len(jobs)}**\n- Speed: **{summary['games_per_second']} games/s**\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "worker_results"}, indent=2))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

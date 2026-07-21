from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_lab import build_policy, read_deck, normalize_selection
from black_engine.factory import build_hybrid_policy


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, p, center + half)


def load_engine(cg_dir: str):
    cg_dir = str(Path(cg_dir).resolve())
    for p in (cg_dir, str(Path(cg_dir).parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from cg.game import battle_start, battle_select, battle_finish
    return battle_start, battle_select, battle_finish


def play_one(battle_start, battle_select, battle_finish, deck, policy_hybrid, policy_base, hybrid_seat: int):
    obs, sd = battle_start(deck[:], deck[:])
    if sd.errorType != 0:
        return {"outcome": "BATTLE_START_ERROR", "crash": True, "invalid": False, "steps": 0}
    steps = 0
    outcome = "UNKNOWN"
    invalid = False
    while True:
        cur = obs.get("current") or {}
        result = cur.get("result", -1)
        if result is not None and result >= 0:
            outcome = "HYBRID_WIN" if result == hybrid_seat else ("DRAW" if result == 2 else "BASE_WIN")
            break
        idx = cur.get("yourIndex")
        sel = obs.get("select") or {}
        opts = sel.get("option") or []
        minc = int(sel.get("minCount", 1) or 0)
        maxc = int(sel.get("maxCount", 1) or 1)
        policy = policy_hybrid if idx == hybrid_seat else policy_base
        try:
            action = policy.agent(obs)
        except Exception as exc:
            return {"outcome": "POLICY_CRASH", "crash": True, "invalid": False, "steps": steps, "error": repr(exc)}
        if not isinstance(action, list):
            action = [action] if isinstance(action, int) else []
        if not (minc <= len(action) <= max(maxc, len(action))) or any(not (0 <= i < len(opts)) for i in action):
            invalid = True
        try:
            obs = battle_select(action)
        except Exception as exc:
            return {"outcome": "ENGINE_CRASH", "crash": True, "invalid": invalid, "steps": steps, "error": repr(exc)}
        steps += 1
        if steps > 800:
            outcome = "STEP_CAP"
            break
    try:
        battle_finish()
    except Exception:
        pass
    return {"outcome": outcome, "crash": False, "invalid": invalid, "steps": steps}


def run_matchup(candidate: str, deck: list[int], n_games: int, cg_dir: str, ablate_env: dict) -> dict:
    battle_start, battle_select, battle_finish = load_engine(cg_dir)
    results = []
    old_env = {k: os.environ.get(k) for k in ablate_env}
    os.environ.update(ablate_env)
    try:
        for g in range(n_games):
            base = build_policy(candidate)
            base.set_deck(deck)
            hybrid_base = build_policy(candidate)
            hybrid = build_hybrid_policy(candidate, hybrid_base, root=ROOT)
            hybrid.set_deck(deck)
            hybrid_seat = g % 2  # alternate seats
            r = play_one(battle_start, battle_select, battle_finish, deck, hybrid, base, hybrid_seat)
            r["game"] = g
            r["hybrid_seat"] = hybrid_seat
            results.append(r)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    n = len(results)
    crashes = sum(1 for r in results if r["crash"])
    invalids = sum(1 for r in results if r["invalid"])
    decided = [r for r in results if r["outcome"] in ("HYBRID_WIN", "BASE_WIN")]
    hybrid_wins = sum(1 for r in decided if r["outcome"] == "HYBRID_WIN")
    n_decided = len(decided)
    lo, p, hi = wilson_ci(hybrid_wins, n_decided) if n_decided else (0.0, 0.0, 0.0)
    return {
        "candidate": candidate, "ablation": ablate_env, "games": n,
        "crashes": crashes, "invalid_actions": invalids,
        "decided": n_decided, "hybrid_wins": hybrid_wins,
        "hybrid_win_rate": p, "wilson_ci95": [lo, hi],
        "outcomes": {k: sum(1 for r in results if r["outcome"] == k) for k in set(r["outcome"] for r in results)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cg-dir", default="/tmp/hros-lowvalue-attack/submission/cg")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "ablation_eval.json"))
    args = ap.parse_args()

    candidates = {
        "mewtwo_spidops": read_deck(ROOT / "candidates" / "mewtwo_spidops" / "deck.csv"),
        "garchomp_spiritomb": read_deck(ROOT / "candidates" / "garchomp_spiritomb" / "deck.csv"),
    }
    ablations = {
        "full_hybrid": {},
        "ablate_guards": {"BLACK_ABLATE_GUARDS": "1"},
        "ablate_bayes": {"BLACK_ABLATE_BAYES": "1"},
        "ablate_rl": {"BLACK_ABLATE_RL": "1"},
        "ablate_ismcts": {"BLACK_ABLATE_ISMCTS": "1"},
    }

    report = {"games_per_cell": args.games, "cells": []}
    t0 = time.time()
    for cand, deck in candidates.items():
        for label, env in ablations.items():
            cell = run_matchup(cand, deck, args.games, args.cg_dir, env)
            cell["label"] = label
            report["cells"].append(cell)
            print(json.dumps({k: cell[k] for k in ("candidate", "label", "games", "crashes", "invalid_actions", "hybrid_win_rate", "wilson_ci95")}), flush=True)
    report["elapsed_seconds"] = round(time.time() - t0, 1)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print("WROTE", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

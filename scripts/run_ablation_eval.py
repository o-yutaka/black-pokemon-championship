from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine import build_candidate_base_policy
from black_engine.factory import build_hybrid_policy
from black_lab import read_deck
from engine.official_runtime import run_battle
from scripts.run_official_smoke import oracle_bank_payload, summarize_decision_trace

CANDIDATES = (
    "mewtwo_spidops",
    "garchomp_spiritomb",
    "dragapult_cinderace",
)
ABLATIONS = {
    "full_hybrid": {},
    "ablate_guards": {"BLACK_ABLATE_GUARDS": "1"},
    "ablate_bayes": {"BLACK_ABLATE_BAYES": "1"},
    "ablate_rl": {"BLACK_ABLATE_RL": "1"},
    "ablate_ismcts": {"BLACK_ABLATE_ISMCTS": "1"},
}


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, p, center + half)


@contextmanager
def patched_environment(values: dict[str, str | None]) -> Iterator[None]:
    old = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _oracle_bank_path(candidate: str, deck: list[int], output_dir: Path) -> Path:
    path = output_dir / f"oracle_{candidate}_mirror.json"
    path.write_text(
        json.dumps(oracle_bank_payload(candidate, deck), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _raw_action_was_normalized(raw_action, action: list[int]) -> bool:
    return raw_action != action


def run_matchup(
    *,
    candidate: str,
    deck: list[int],
    n_games: int,
    cg_dir: str,
    ablation_label: str,
    ablate_env: dict[str, str],
    belief_mode: str,
    output_dir: Path,
    max_steps: int,
) -> dict:
    trace_path = output_dir / f"{candidate}.{belief_mode}.{ablation_label}.decision_trace.jsonl"
    trace_path.unlink(missing_ok=True)
    bank_path = _oracle_bank_path(candidate, deck, output_dir) if belief_mode == "oracle" else None
    environment: dict[str, str | None] = {
        "CABT_CG_DIR": str(Path(cg_dir).resolve()),
        "BLACK_BELIEF_BANK": str(bank_path) if bank_path else None,
        "BLACK_DECISION_TRACE": str(trace_path),
        "BLACK_ISMCTS": "1",
        "BLACK_ABLATE_GUARDS": None,
        "BLACK_ABLATE_BAYES": None,
        "BLACK_ABLATE_RL": None,
        "BLACK_ABLATE_ISMCTS": None,
        **ablate_env,
    }

    results: list[dict] = []
    normalization_events = 0
    with patched_environment(environment):
        for game in range(n_games):
            base = build_candidate_base_policy(candidate)
            base.set_deck(deck)
            hybrid_base = build_candidate_base_policy(candidate)
            hybrid = build_hybrid_policy(candidate, hybrid_base, root=ROOT)
            hybrid.set_deck(deck)
            hybrid.trace_path = trace_path
            hybrid_seat = game % 2

            def observe(obs, actor, raw_action, action, decision_ms):
                nonlocal normalization_events
                if actor == hybrid_seat:
                    normalization_events += int(_raw_action_was_normalized(raw_action, action))

            if hybrid_seat == 0:
                report = run_battle(
                    deck,
                    hybrid.agent,
                    deck,
                    base.agent,
                    cg_dir=cg_dir,
                    max_steps=max_steps,
                    decision_observer=observe,
                    game_index=game,
                )
            else:
                report = run_battle(
                    deck,
                    base.agent,
                    deck,
                    hybrid.agent,
                    cg_dir=cg_dir,
                    max_steps=max_steps,
                    decision_observer=observe,
                    game_index=game,
                )

            result = report.get("result", -1)
            outcome = (
                "HYBRID_WIN"
                if report.get("completed") and result == hybrid_seat
                else "BASE_WIN"
                if report.get("completed") and result in (0, 1)
                else "ERROR"
            )
            results.append(
                {
                    "game": game,
                    "hybrid_seat": hybrid_seat,
                    "outcome": outcome,
                    **report,
                }
            )

    n = len(results)
    errors = sum(1 for result in results if result["outcome"] == "ERROR")
    decided = [result for result in results if result["outcome"] in ("HYBRID_WIN", "BASE_WIN")]
    hybrid_wins = sum(1 for result in decided if result["outcome"] == "HYBRID_WIN")
    n_decided = len(decided)
    lo, p, hi = wilson_ci(hybrid_wins, n_decided) if n_decided else (0.0, 0.0, 0.0)
    trace = summarize_decision_trace(trace_path).get(candidate, {})
    return {
        "candidate": candidate,
        "label": ablation_label,
        "ablation": ablate_env,
        "belief_mode": belief_mode,
        "oracle_quality_template": belief_mode == "oracle",
        "production_evidence": False if belief_mode == "oracle" else None,
        "games": n,
        "errors": errors,
        "decided": n_decided,
        "hybrid_wins": hybrid_wins,
        "hybrid_win_rate": p,
        "wilson_ci95": [lo, hi],
        "seat_policy": "alternating",
        "seed_control": "UNAVAILABLE_IN_OFFICIAL_BATTLE_START",
        "paired_seed_claim": False,
        "normalization_events": normalization_events,
        "trace": trace,
        "outcomes": dict(Counter(result["outcome"] for result in results)),
        "records": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seat-balanced deterministic-base ablation on the real official engine."
    )
    parser.add_argument("--cg-dir", default="/home/user/HROS/submission/cg")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--candidate", action="append", choices=CANDIDATES)
    parser.add_argument("--label", action="append", choices=tuple(ABLATIONS))
    parser.add_argument("--belief-mode", choices=("default", "oracle"), default="default")
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "ablation_eval.json"))
    args = parser.parse_args()
    if args.games <= 0:
        raise SystemExit("--games must be positive")

    candidates = tuple(dict.fromkeys(args.candidate or CANDIDATES))
    labels = tuple(dict.fromkeys(args.label or tuple(ABLATIONS)))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "games_per_cell": args.games,
        "belief_mode": args.belief_mode,
        "seat_policy": "alternating",
        "seed_control": "UNAVAILABLE_IN_OFFICIAL_BATTLE_START",
        "paired_seed_claim": False,
        "cells": [],
    }
    started = time.time()
    for candidate in candidates:
        deck = read_deck(ROOT / "candidates" / candidate / "deck.csv")
        if len(deck) != 60:
            raise RuntimeError(f"{candidate}: deck size={len(deck)}")
        for label in labels:
            cell = run_matchup(
                candidate=candidate,
                deck=deck,
                n_games=args.games,
                cg_dir=args.cg_dir,
                ablation_label=label,
                ablate_env=ABLATIONS[label],
                belief_mode=args.belief_mode,
                output_dir=out_path.parent,
                max_steps=args.max_steps,
            )
            report["cells"].append(cell)
            print(
                json.dumps(
                    {
                        key: cell[key]
                        for key in (
                            "candidate",
                            "label",
                            "belief_mode",
                            "games",
                            "errors",
                            "hybrid_win_rate",
                            "wilson_ci95",
                            "normalization_events",
                        )
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    report["elapsed_seconds"] = round(time.time() - started, 3)
    report["verdict"] = (
        "PASS_NO_RUNTIME_ERRORS"
        if all(int(cell["errors"]) == 0 for cell in report["cells"])
        else "FAIL_RUNTIME_ERRORS"
    )
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {out_path}")
    return 0 if report["verdict"] == "PASS_NO_RUNTIME_ERRORS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

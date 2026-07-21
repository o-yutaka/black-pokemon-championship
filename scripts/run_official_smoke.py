from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from itertools import combinations
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.factory import build_hybrid_policy
from black_engine.mewtwo_policy import MEWTWO_ERASURE_BALL, MEWTWO_EX
from black_engine.official_observation import (
    BLACK_ATTACHED_ENERGY_MARKER,
    normalize_official_observation,
)
from black_engine.rocket_ledger import BASIC_ENERGY_IDS, TEAM_ROCKET_ENERGY
from black_engine.truth import TruthState, build_truth_state
from black_lab import build_policy, read_deck
from engine.official_runtime import run_battle

CANDIDATES = (
    "mewtwo_spidops",
    "garchomp_spiritomb",
    "dragapult_cinderace",
)


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


def candidate_deck(name: str) -> list[int]:
    if name not in CANDIDATES:
        raise ValueError(f"unknown candidate: {name}")
    deck = read_deck(ROOT / "candidates" / name / "deck.csv")
    if len(deck) != 60:
        raise RuntimeError(f"{name}: deck size={len(deck)}")
    return deck


def oracle_bank_payload(opponent_name: str, opponent_deck: list[int]) -> dict:
    if opponent_name not in CANDIDATES:
        raise ValueError(f"unknown opponent candidate: {opponent_name}")
    if len(opponent_deck) != 60:
        raise ValueError(f"oracle deck must contain 60 cards, got {len(opponent_deck)}")
    return {
        "version": 1,
        "status": "ORACLE_RESEARCH_ONLY",
        "production_evidence": False,
        "templates": [
            {
                "name": f"oracle_{opponent_name}",
                "deck": list(opponent_deck),
                "prior": 1.0,
            }
        ],
    }


def _write_oracle_bank(output_dir: Path, owner: str, opponent: str, deck: list[int]) -> Path:
    path = output_dir / f"oracle_{owner}_vs_{opponent}.json"
    path.write_text(
        json.dumps(oracle_bank_payload(opponent, deck), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_agent(
    name: str,
    *,
    opponent_name: str,
    opponent_deck: list[int],
    own_deck: list[int],
    belief_mode: str,
    cg_dir: str,
    output_dir: Path,
    trace_path: Path,
):
    bank_path = None
    if belief_mode == "oracle":
        bank_path = _write_oracle_bank(output_dir, name, opponent_name, opponent_deck)
    environment = {
        "CABT_CG_DIR": str(Path(cg_dir).resolve()),
        "BLACK_BELIEF_BANK": str(bank_path) if bank_path else None,
        "BLACK_ISMCTS": "1",
    }
    with patched_environment(environment):
        base = build_policy(name)
        policy = build_hybrid_policy(name, base, root=ROOT)
    policy.set_deck(own_deck)
    policy.trace_path = trace_path
    return policy.agent


def _card_id(value: Any) -> int:
    if type(value) is int:
        return value
    if isinstance(value, dict):
        for key in ("id", "card", "cardId", "pokemonId"):
            card = value.get(key)
            if type(card) is int:
                return card
    return -1


def effect_shape(obs: dict) -> dict | None:
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    effect = select.get("effect")
    if not isinstance(effect, dict):
        return None
    return {
        key: effect[key]
        for key in ("id", "serial", "playerIndex")
        if key in effect and type(effect[key]) in (int, str)
    }


def option_shape(option) -> dict:
    raw = option.raw
    synthetic_attached = bool(raw.get(BLACK_ATTACHED_ENERGY_MARKER))
    official_raw_keys = sorted(
        str(key)
        for key in raw
        if key != BLACK_ATTACHED_ENERGY_MARKER
        and not (synthetic_attached and key in {"card", "target"})
    )
    return {
        "index": option.index,
        "raw_keys": official_raw_keys,
        "normalized_keys": sorted(str(key) for key in raw),
        "type": raw.get("type"),
        "area": raw.get("area"),
        "raw_index": raw.get("index"),
        "energyIndex": raw.get("energyIndex"),
        "inPlayArea": raw.get("inPlayArea"),
        "inPlayIndex": raw.get("inPlayIndex"),
        "playerIndex": raw.get("playerIndex"),
        "attackId": option.attack_id,
        "resolved_card_id": option.card_id,
        "resolved_target_id": option.target_id,
        "signature": option.signature,
    }


def classify_mewtwo_shape(candidate: str, truth: TruthState, obs: dict) -> str | None:
    if candidate != "mewtwo_spidops":
        return None
    if any(option.attack_id == MEWTWO_ERASURE_BALL for option in truth.options):
        return "ERASURE_ATTACK_OPTION"
    energy_ids = set(BASIC_ENERGY_IDS) | {TEAM_ROCKET_ENERGY}
    energy_options = [option for option in truth.options if option.card_id in energy_ids]
    effect = effect_shape(obs)
    if (
        truth.select_type == 2
        and truth.select_context == 26
        and truth.min_count == 0
        and truth.max_count == 2
        and effect
        and _card_id(effect) == MEWTWO_EX
        and energy_options
    ):
        return "ERASURE_DISCARD_WINDOW"
    if effect and _card_id(effect) == MEWTWO_EX:
        return "MEWTWO_SELECT_EFFECT"
    return None


def option_shape_record(
    *,
    candidate: str,
    opponent: str,
    game: int,
    step: int,
    truth: TruthState,
    obs: dict,
    action: list[int],
    decision_ms: float,
) -> dict | None:
    tag = classify_mewtwo_shape(candidate, truth, obs)
    if tag is None:
        return None
    return {
        "candidate": candidate,
        "opponent": opponent,
        "game": game,
        "step": step,
        "turn": truth.turn,
        "actor": truth.actor,
        "tag": tag,
        "decision_ms": round(decision_ms, 6),
        "select": {
            "type": truth.select_type,
            "context": truth.select_context,
            "minCount": truth.min_count,
            "maxCount": truth.max_count,
            "effect": effect_shape(obs),
        },
        "options": [option_shape(option) for option in truth.options],
        "chosen_indices": list(action),
    }


def summarize_decision_trace(path: Path) -> dict:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "records": 0,
            "search_enabled": 0,
            "search_disabled": 0,
            "simulations": 0,
            "fallback_used": 0,
            "reasons": Counter(),
        }
    )
    if not path.is_file():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        candidate = str(payload.get("candidate", "UNKNOWN"))
        row = grouped[candidate]
        search = payload.get("search") if isinstance(payload.get("search"), dict) else {}
        row["records"] += 1
        enabled = bool(search.get("enabled"))
        row["search_enabled"] += int(enabled)
        row["search_disabled"] += int(not enabled)
        row["simulations"] += int(search.get("simulations", 0) or 0)
        row["fallback_used"] += int(bool(payload.get("fallback_used")))
        row["reasons"][str(search.get("reason", ""))] += 1
    return {
        candidate: {
            **{key: value for key, value in row.items() if key != "reasons"},
            "reasons": dict(row["reasons"]),
        }
        for candidate, row in grouped.items()
    }


def pairings(candidates: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    if len(candidates) == 1:
        return ((candidates[0], candidates[0]),)
    return tuple(combinations(candidates, 2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run real CABT smoke, three-candidate round robin, and exact Mewtwo option capture."
    )
    parser.add_argument("--cg-dir", default="/home/user/HROS/submission/cg")
    parser.add_argument("--candidate", action="append", choices=CANDIDATES)
    parser.add_argument("--games", type=int, default=20, help="games per candidate pair")
    parser.add_argument("--belief-mode", choices=("default", "oracle"), default="default")
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "official_smoke.json"))
    parser.add_argument(
        "--capture-out",
        default=str(ROOT / "artifacts" / "mewtwo_option_shapes.jsonl"),
    )
    parser.add_argument("--require-search", action="store_true")
    parser.add_argument("--require-mewtwo-shape", action="store_true")
    args = parser.parse_args()
    if args.games <= 0:
        raise SystemExit("--games must be positive")

    selected = tuple(dict.fromkeys(args.candidate or CANDIDATES))
    decks = {name: candidate_deck(name) for name in selected}
    output = Path(args.out)
    capture_output = Path(args.capture_out)
    trace_dir = output.parent / (output.stem + "_traces")
    decision_trace = output.parent / (output.stem + "_hybrid_decisions.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    capture_output.parent.mkdir(parents=True, exist_ok=True)
    decision_trace.unlink(missing_ok=True)

    wins = {name: 0 for name in selected}
    errors = 0
    games: list[dict] = []
    captures: list[dict] = []
    provenance = None
    started = time.time()

    with patched_environment({"CABT_CG_DIR": str(Path(args.cg_dir).resolve())}):
        for left, right in pairings(selected):
            for index in range(args.games):
                reversed_seats = index % 2 == 1
                name0, name1 = (right, left) if reversed_seats else (left, right)
                deck0, deck1 = decks[name0], decks[name1]
                agent0 = build_agent(
                    name0,
                    opponent_name=name1,
                    opponent_deck=deck1,
                    own_deck=deck0,
                    belief_mode=args.belief_mode,
                    cg_dir=args.cg_dir,
                    output_dir=output.parent,
                    trace_path=decision_trace,
                )
                agent1 = build_agent(
                    name1,
                    opponent_name=name0,
                    opponent_deck=deck0,
                    own_deck=deck1,
                    belief_mode=args.belief_mode,
                    cg_dir=args.cg_dir,
                    output_dir=output.parent,
                    trace_path=decision_trace,
                )
                local_step = 0

                def observe(obs, actor, raw_action, action, decision_ms):
                    nonlocal local_step
                    actor_name = name0 if actor == 0 else name1
                    opponent_name = name1 if actor == 0 else name0
                    truth = build_truth_state(normalize_official_observation(obs))
                    record = option_shape_record(
                        candidate=actor_name,
                        opponent=opponent_name,
                        game=len(games),
                        step=local_step,
                        truth=truth,
                        obs=obs,
                        action=action,
                        decision_ms=decision_ms,
                    )
                    if record is not None:
                        captures.append(record)
                    local_step += 1

                report = run_battle(
                    deck0,
                    agent0,
                    deck1,
                    agent1,
                    cg_dir=args.cg_dir,
                    max_steps=args.max_steps,
                    trace_path=trace_dir / f"game_{len(games):04d}.jsonl",
                    decision_observer=observe,
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
                        "game": len(games),
                        "pair": [left, right],
                        "pair_game": index,
                        "seat0": name0,
                        "seat1": name1,
                        "winner": winner,
                        **report,
                    }
                )

    with capture_output.open("w", encoding="utf-8") as handle:
        for record in captures:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    decision_summary = summarize_decision_trace(decision_trace)
    search_enabled = sum(int(row.get("search_enabled", 0)) for row in decision_summary.values())
    mewtwo_shape_counts = Counter(record["tag"] for record in captures)
    requirements = {
        "runtime_errors_zero": errors == 0,
        "search_executed": (not args.require_search) or search_enabled > 0,
        "mewtwo_shape_captured": (not args.require_mewtwo_shape) or bool(captures),
    }
    summary = {
        "verdict": "OFFICIAL_SMOKE_PASS" if all(requirements.values()) else "OFFICIAL_SMOKE_FAIL",
        "belief_mode": args.belief_mode,
        "oracle_quality_template": args.belief_mode == "oracle",
        "production_evidence": False if args.belief_mode == "oracle" else None,
        "candidates": list(selected),
        "games_per_pair": args.games,
        "pairs": [list(pair) for pair in pairings(selected)],
        "games_requested": args.games * len(pairings(selected)),
        "games_completed": len(games) - errors,
        "errors": errors,
        "wins": wins,
        "seat_policy": "alternating",
        "seed_control": "UNAVAILABLE_IN_OFFICIAL_BATTLE_START",
        "paired_seed_claim": False,
        "provenance": provenance,
        "decision_trace": str(decision_trace),
        "decision_summary": decision_summary,
        "search_enabled_records": search_enabled,
        "mewtwo_option_capture": {
            "path": str(capture_output),
            "records": len(captures),
            "tags": dict(mewtwo_shape_counts),
        },
        "requirements": requirements,
        "elapsed_seconds": round(time.time() - started, 3),
        "records": games,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, ensure_ascii=False, indent=2))
    return 0 if summary["verdict"] == "OFFICIAL_SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

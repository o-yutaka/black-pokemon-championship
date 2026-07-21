from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.official_observation import normalize_official_observation
from black_engine.truth import TruthState, build_truth_state
from black_lab import read_deck
from engine.official_runtime import run_battle
from scripts.build_official_hybrid_submission import stage_submission
from scripts.run_official_smoke import (
    CANDIDATES,
    build_agent,
    candidate_deck,
    oracle_bank_payload,
    patched_environment,
)
from submission_contract import validate_runtime_layout

DRAGAPULT = "dragapult_cinderace"
DRAKLOAK, DRAGAPULT_EX, DUSCLOPS, DUSKNOIR, CINDERACE = 120, 121, 132, 133, 666
RARE_CANDY, CRISPIN = 1079, 1198
PHANTOM_DIVE, TURBO_FLARE = 154, 965

REQUIRED_GROUPS = {
    "RECON_DIRECTIVE": {"RECON_ACTIVATE", "RECON_TO_HAND", "RECON_TO_DECK_BOTTOM"},
    "RARE_CANDY": {"RARE_CANDY_EVOLVE"},
    "CRISPIN": {"CRISPIN_TO_HAND", "CRISPIN_ATTACH_TARGET"},
    "TURBO_FLARE": {"TURBO_FLARE_ATTACK", "TURBO_FLARE_ENERGY", "TURBO_FLARE_TARGET"},
    "PHANTOM_DIVE": {"PHANTOM_DIVE_ATTACK", "PHANTOM_DIVE_COUNTER"},
    "DUSCLOPS": {"DUSCLOPS_COUNTER"},
    "DUSKNOIR": {"DUSKNOIR_COUNTER"},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _effect_id(obs: dict) -> int:
    select = obs.get("select") if isinstance(obs.get("select"), dict) else {}
    effect = select.get("effect")
    if isinstance(effect, dict):
        value = effect.get("id")
        return value if type(value) is int else -1
    return -1


def classify_dragapult_transition(truth: TruthState, obs: dict) -> tuple[str, ...]:
    tags: list[str] = []
    context = truth.select_context
    effect = _effect_id(obs)
    if any(option.attack_id == PHANTOM_DIVE for option in truth.options):
        tags.append("PHANTOM_DIVE_ATTACK")
    if any(option.attack_id == TURBO_FLARE for option in truth.options):
        tags.append("TURBO_FLARE_ATTACK")
    if effect == DRAKLOAK:
        tags.append({43: "RECON_ACTIVATE", 7: "RECON_TO_HAND", 10: "RECON_TO_DECK_BOTTOM"}.get(context, "RECON_OTHER"))
    elif effect == RARE_CANDY and context == 37:
        tags.append("RARE_CANDY_EVOLVE")
    elif effect == CRISPIN:
        if context == 7:
            tags.append("CRISPIN_TO_HAND")
        elif context == 21:
            tags.append("CRISPIN_ATTACH_FROM")
        elif context in {22, 25}:
            tags.append("CRISPIN_ATTACH_TARGET")
        else:
            tags.append("CRISPIN_OTHER")
    elif effect == CINDERACE:
        if context == 21:
            tags.append("TURBO_FLARE_ENERGY")
        elif context in {22, 25}:
            tags.append("TURBO_FLARE_TARGET")
        else:
            tags.append("CINDERACE_OTHER")
    elif effect == DRAGAPULT_EX and context == 14:
        tags.append("PHANTOM_DIVE_COUNTER")
    elif effect == DUSCLOPS and context == 13:
        tags.append("DUSCLOPS_COUNTER")
    elif effect == DUSKNOIR and context == 13:
        tags.append("DUSKNOIR_COUNTER")
    return tuple(dict.fromkeys(tags))


def _capture_record(
    *,
    game: int,
    step: int,
    opponent: str,
    seat: int,
    truth: TruthState,
    obs: dict,
    raw_action: Any,
    action: list[int],
    decision_ms: float,
    tags: tuple[str, ...],
) -> dict:
    return {
        "game": game,
        "step": step,
        "candidate": DRAGAPULT,
        "opponent": opponent,
        "seat": seat,
        "turn": truth.turn,
        "actor": truth.actor,
        "tags": list(tags),
        "decision_ms": round(decision_ms, 6),
        "raw_action": raw_action,
        "chosen_indices": list(action),
        "select": obs.get("select"),
        "current": obs.get("current"),
        "logs": obs.get("logs"),
    }


def _load_packaged_dragapult_agent(
    package_root: Path,
    *,
    opponent_name: str,
    opponent_deck: list[int],
    belief_mode: str,
    output_dir: Path,
    trace_path: Path,
    module_token: str,
):
    bank_path = None
    if belief_mode == "oracle":
        bank_path = output_dir / f"oracle_packaged_dragapult_vs_{opponent_name}.json"
        bank_path.write_text(
            json.dumps(oracle_bank_payload(opponent_name, opponent_deck), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    environment = {
        "CABT_CG_DIR": str((package_root / "cg").resolve()),
        "BLACK_BELIEF_BANK": str(bank_path) if bank_path else None,
        "BLACK_ISMCTS": "1",
    }
    with patched_environment(environment):
        package_text = str(package_root)
        inserted = package_text not in sys.path
        if inserted:
            sys.path.insert(0, package_text)
        try:
            spec = importlib.util.spec_from_file_location(
                f"black_submission_main_{module_token}",
                package_root / "main.py",
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("unable to load staged submission/main.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if inserted and sys.path and sys.path[0] == package_text:
                sys.path.pop(0)
    if Path(module.ROOT).resolve() != package_root.resolve():
        raise RuntimeError(f"packaged main resolved wrong root: {module.ROOT}")
    if module.CANDIDATE != DRAGAPULT:
        raise RuntimeError(f"packaged candidate mismatch: {module.CANDIDATE}")
    if module.DECK != read_deck(package_root / "deck.csv"):
        raise RuntimeError("packaged main deck differs from staged deck.csv")
    module.HYBRID_POLICY.trace_path = trace_path
    return module.agent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Official CABT packaged-submission Dragapult route capture and smoke gate."
    )
    parser.add_argument("--cg-dir", default="/home/user/HROS/submission/cg")
    parser.add_argument("--opponent", action="append", choices=tuple(name for name in CANDIDATES if name != DRAGAPULT))
    parser.add_argument("--games", type=int, default=40, help="games per opponent; seats alternate")
    parser.add_argument("--belief-mode", choices=("default", "oracle"), default="oracle")
    parser.add_argument("--max-steps", type=int, default=20000)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "dragapult_complete_smoke.json"))
    parser.add_argument("--capture-out", default=str(ROOT / "artifacts" / "dragapult_complete_transitions.jsonl"))
    parser.add_argument("--require-all-routes", action="store_true")
    args = parser.parse_args()
    if args.games <= 0:
        raise SystemExit("--games must be positive")

    opponents = tuple(dict.fromkeys(args.opponent or ("mewtwo_spidops", "garchomp_spiritomb")))
    output = Path(args.out).resolve()
    capture_output = Path(args.capture_out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    capture_output.parent.mkdir(parents=True, exist_ok=True)

    package_root = output.parent / f".{output.stem}_submission"
    stage_submission(Path(args.cg_dir), package_root)
    package_report = validate_runtime_layout(package_root)
    dragapult_deck = read_deck(package_root / "deck.csv")
    if dragapult_deck != read_deck(ROOT / "deck.csv"):
        raise SystemExit("packaged deck drifted from canonical repository-root deck.csv")
    opponent_decks = {name: candidate_deck(name) for name in opponents}

    records: list[dict] = []
    games: list[dict] = []
    tags = Counter()
    errors = 0
    wins = Counter()
    provenance = None
    started = time.time()
    trace_path = output.parent / "dragapult_complete_hybrid_decisions.jsonl"

    with patched_environment({"CABT_CG_DIR": str((package_root / "cg").resolve())}):
        for opponent in opponents:
            opponent_deck = opponent_decks[opponent]
            for pair_game in range(args.games):
                dragapult_seat = pair_game % 2
                if dragapult_seat == 0:
                    name0, deck0 = DRAGAPULT, dragapult_deck
                    name1, deck1 = opponent, opponent_deck
                else:
                    name0, deck0 = opponent, opponent_deck
                    name1, deck1 = DRAGAPULT, dragapult_deck

                if name0 == DRAGAPULT:
                    agent0 = _load_packaged_dragapult_agent(
                        package_root,
                        opponent_name=name1,
                        opponent_deck=deck1,
                        belief_mode=args.belief_mode,
                        output_dir=output.parent,
                        trace_path=trace_path,
                        module_token=f"{len(games)}_seat0",
                    )
                else:
                    agent0 = build_agent(
                        name0,
                        opponent_name=name1,
                        opponent_deck=deck1,
                        own_deck=deck0,
                        belief_mode=args.belief_mode,
                        cg_dir=str(package_root / "cg"),
                        output_dir=output.parent,
                        trace_path=trace_path,
                    )
                if name1 == DRAGAPULT:
                    agent1 = _load_packaged_dragapult_agent(
                        package_root,
                        opponent_name=name0,
                        opponent_deck=deck0,
                        belief_mode=args.belief_mode,
                        output_dir=output.parent,
                        trace_path=trace_path,
                        module_token=f"{len(games)}_seat1",
                    )
                else:
                    agent1 = build_agent(
                        name1,
                        opponent_name=name0,
                        opponent_deck=deck0,
                        own_deck=deck1,
                        belief_mode=args.belief_mode,
                        cg_dir=str(package_root / "cg"),
                        output_dir=output.parent,
                        trace_path=trace_path,
                    )
                local_step = 0

                def observe(obs, actor, raw_action, action, decision_ms):
                    nonlocal local_step
                    actor_name = name0 if actor == 0 else name1
                    if actor_name == DRAGAPULT:
                        truth = build_truth_state(normalize_official_observation(obs))
                        found = classify_dragapult_transition(truth, obs)
                        if found:
                            records.append(_capture_record(
                                game=len(games),
                                step=local_step,
                                opponent=opponent,
                                seat=actor,
                                truth=truth,
                                obs=obs,
                                raw_action=raw_action,
                                action=action,
                                decision_ms=decision_ms,
                                tags=found,
                            ))
                            tags.update(found)
                    local_step += 1

                report = run_battle(
                    deck0,
                    agent0,
                    deck1,
                    agent1,
                    cg_dir=package_root / "cg",
                    max_steps=args.max_steps,
                    trace_path=output.parent / "dragapult_complete_traces" / f"game_{len(games):04d}.jsonl",
                    decision_observer=observe,
                    game_index=len(games),
                )
                provenance = provenance or report.get("provenance")
                winner = None
                if report.get("completed") and report.get("result") in (0, 1):
                    winner = name0 if report["result"] == 0 else name1
                    wins[winner] += 1
                else:
                    errors += 1
                games.append({
                    "game": len(games),
                    "opponent": opponent,
                    "pair_game": pair_game,
                    "dragapult_seat": dragapult_seat,
                    "winner": winner,
                    **report,
                })

    with capture_output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    observed = set(tags)
    route_groups = {
        group: {
            "required_tags": sorted(required),
            "observed_tags": sorted(required & observed),
            "complete": required <= observed,
        }
        for group, required in REQUIRED_GROUPS.items()
    }
    requirements = {
        "submission_runtime_layout": package_report.get("runtime") == "PASS",
        "canonical_main_byte_identity": (ROOT / "main.py").read_bytes() == (package_root / "main.py").read_bytes(),
        "canonical_deck_byte_identity": (ROOT / "deck.csv").read_bytes() == (package_root / "deck.csv").read_bytes(),
        "runtime_errors_zero": errors == 0,
        "all_routes_captured": (not args.require_all_routes) or all(row["complete"] for row in route_groups.values()),
    }
    summary = {
        "verdict": "DRAGAPULT_COMPLETE_SMOKE_PASS" if all(requirements.values()) else "DRAGAPULT_COMPLETE_SMOKE_FAIL",
        "execution_surface": "STAGED_EXACT_SUBMISSION_MAIN",
        "submission_package": {
            **package_report,
            "path": str(package_root),
            "main_sha256": _sha256(package_root / "main.py"),
            "deck_sha256": _sha256(package_root / "deck.csv"),
            "libcg_sha256": _sha256(package_root / "cg" / "libcg.so"),
        },
        "belief_mode": args.belief_mode,
        "production_evidence": False if args.belief_mode == "oracle" else None,
        "games_per_opponent": args.games,
        "opponents": list(opponents),
        "games_requested": args.games * len(opponents),
        "games_completed": len(games) - errors,
        "errors": errors,
        "wins": dict(wins),
        "seat_policy": "alternating",
        "seed_control": "UNAVAILABLE_IN_OFFICIAL_BATTLE_START",
        "paired_seed_claim": False,
        "provenance": provenance,
        "transition_capture": {
            "path": str(capture_output),
            "records": len(records),
            "tags": dict(tags),
            "route_groups": route_groups,
        },
        "requirements": requirements,
        "elapsed_seconds": round(time.time() - started, 3),
        "records": games,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, ensure_ascii=False, indent=2))
    return 0 if summary["verdict"] == "DRAGAPULT_COMPLETE_SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

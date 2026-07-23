from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.bundles import tree_sha256
from black_engine.evaluation.official_runner import run_matchup


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seat-balanced official-engine Bundle-vs-Bundle Red Team runner.")
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--candidate-bundle", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path, help="Locked manifest produced by build_red_team_bundles.py")
    parser.add_argument("--matchup", action="append", help="Run only selected slug; may be repeated.")
    parser.add_argument("--out-dir", default=ROOT / "artifacts" / "official_red_team", type=Path)
    parser.add_argument("--games", type=int, help="Override manifest game count; must equal the locked requirement for promotion.")
    parser.add_argument("--decision-timeout-ms", type=float, default=1000.0)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    promotion = manifest.get("promotion") if isinstance(manifest.get("promotion"), dict) else {}
    selected = set(args.matchup or promotion.get("required_matchups") or [])
    if not selected:
        raise SystemExit("no locked required matchups selected")

    candidate_hash = tree_sha256(args.candidate_bundle)
    engine_path = args.cg_dir.resolve() / "libcg.so"
    if not engine_path.is_file():
        raise FileNotFoundError(engine_path)
    engine_hash = file_sha256(engine_path)
    expected_candidate = promotion.get("candidate_bundle_sha256")
    expected_engine = promotion.get("engine_sha256")
    if expected_candidate in (None, "", "REQUIRED_BEFORE_RUN") or candidate_hash != expected_candidate:
        raise SystemExit(f"candidate SHA not locked/matched expected={expected_candidate} actual={candidate_hash}")
    if expected_engine in (None, "", "REQUIRED_BEFORE_RUN") or engine_hash != expected_engine:
        raise SystemExit(f"engine SHA not locked/matched expected={expected_engine} actual={engine_hash}")

    print(json.dumps({"candidate_bundle": str(args.candidate_bundle.resolve()), "candidate_sha256": candidate_hash, "engine_sha256": engine_hash}, indent=2))
    failures = 0
    for slug in selected:
        config = (manifest.get("matchups") or {}).get(slug)
        if not isinstance(config, dict):
            print(f"{slug}: FAIL missing locked matchup config", file=sys.stderr)
            failures += 1
            continue
        bundle_path = Path(config["bundle_path"])
        bundle = bundle_path.resolve() if bundle_path.is_absolute() else (ROOT / bundle_path).resolve()
        if not bundle.is_dir():
            print(f"{slug}: FAIL missing real opponent Bundle: {bundle}", file=sys.stderr)
            failures += 1
            continue
        actual_hash = tree_sha256(bundle)
        expected_hash = config.get("bundle_sha256")
        if expected_hash in (None, "", "REQUIRED_BEFORE_RUN"):
            print(f"{slug}: FAIL manifest hash not frozen; actual={actual_hash}", file=sys.stderr)
            failures += 1
            continue
        if actual_hash != expected_hash:
            print(f"{slug}: FAIL bundle hash mismatch expected={expected_hash} actual={actual_hash}", file=sys.stderr)
            failures += 1
            continue
        required_games = int(config.get("minimum_games", 200))
        games = args.games if args.games is not None else required_games
        if games != required_games:
            print(f"{slug}: FAIL games must equal locked block expected={required_games} actual={games}", file=sys.stderr)
            failures += 1
            continue
        summary = run_matchup(
            matchup=slug,
            cg_dir=args.cg_dir,
            candidate_bundle=args.candidate_bundle,
            opponent_bundle=bundle,
            games=games,
            out_dir=args.out_dir / slug,
            evidence_mode="PROMOTION",
            decision_timeout_ms=args.decision_timeout_ms,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        if not summary.runtime.clean:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

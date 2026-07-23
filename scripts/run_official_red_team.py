from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.bundles import tree_sha256
from black_engine.evaluation.official_runner import run_matchup


def main() -> int:
    parser = argparse.ArgumentParser(description="Seat-balanced official-engine Bundle-vs-Bundle Red Team runner.")
    parser.add_argument("--cg-dir", required=True, type=Path)
    parser.add_argument("--candidate-bundle", required=True, type=Path)
    parser.add_argument("--manifest", default=ROOT / "red_team" / "manifest.json", type=Path)
    parser.add_argument("--matchup", action="append", help="Run only selected slug; may be repeated.")
    parser.add_argument("--out-dir", default=ROOT / "artifacts" / "official_red_team", type=Path)
    parser.add_argument("--games", type=int, help="Override manifest game count; must be even.")
    parser.add_argument("--decision-timeout-ms", type=float, default=1000.0)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = set(args.matchup or (manifest.get("matchups") or {}).keys())
    candidate_hash = tree_sha256(args.candidate_bundle)
    print(json.dumps({"candidate_bundle": str(args.candidate_bundle.resolve()), "candidate_sha256": candidate_hash}, indent=2))

    failures = 0
    for slug, config in (manifest.get("matchups") or {}).items():
        if slug not in selected:
            continue
        bundle = (ROOT / config["bundle_path"]).resolve()
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
        games = args.games or int(config.get("minimum_games", 200))
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

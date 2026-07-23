from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.promotion import evaluate_promotion, load_summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed unless every official championship promotion gate passes.")
    parser.add_argument("--manifest", default=ROOT / "red_team" / "manifest.json", type=Path)
    parser.add_argument("--results", default=ROOT / "artifacts" / "official_red_team", type=Path)
    parser.add_argument("--replay-summary", default=ROOT / "artifacts" / "replay_judge" / "summary.json", type=Path)
    parser.add_argument("--out", default=ROOT / "artifacts" / "promotion_verdict.json", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    replay_summary = (
        json.loads(args.replay_summary.read_text(encoding="utf-8"))
        if args.replay_summary.is_file()
        else None
    )
    verdict = evaluate_promotion(manifest, load_summaries(args.results), replay_summary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(verdict.to_dict(), ensure_ascii=False, indent=2))
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

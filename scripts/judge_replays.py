from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.replay_judge import audit_episode


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit official Kaggle CABT replays against championship hard contracts.")
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--agent-name", default="ジェニファー")
    parser.add_argument("--out-dir", default=ROOT / "artifacts" / "replay_judge", type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audits = []
    counts: Counter[str] = Counter()
    for path in args.replays:
        audit = audit_episode(path, args.agent_name)
        audits.append(audit)
        counts.update(audit.metadata.get("finding_counts", {}))
        (args.out_dir / f"{audit.episode_id}.json").write_text(
            json.dumps(audit.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    overall = sum(value.overall_score for value in audits) / len(audits) if audits else 0.0
    summary = {
        "episodes": len(audits),
        "wins": sum(value.result == "WIN" for value in audits),
        "losses": sum(value.result == "LOSS" for value in audits),
        "mean_overall_score": overall,
        "finding_counts": dict(counts),
        "fatal": sum(f.severity == "FATAL" for a in audits for f in a.findings),
        "major": sum(f.severity == "MAJOR" for a in audits for f in a.findings),
        "minor": sum(f.severity == "MINOR" for a in audits for f in a.findings),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

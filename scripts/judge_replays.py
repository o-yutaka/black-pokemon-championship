from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.replay_judge import audit_episode
from black_engine.evaluation.taxonomy import CANONICAL_FAILURE_CODES


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit post-fix official Kaggle CABT replays against championship hard contracts.")
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--agent-name", default="ジェニファー")
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--corpus-kind", choices=("POST_FIX_HOLDOUT", "TRAINING_REPLAY", "DIAGNOSTIC"), required=True)
    parser.add_argument("--out-dir", default=ROOT / "artifacts" / "replay_judge", type=Path)
    args = parser.parse_args()
    if len(args.candidate_sha256) != 64:
        raise SystemExit("candidate-sha256 must be a 64-character SHA-256 digest")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    audits = []
    counts: Counter[str] = Counter()
    canonical: Counter[str] = Counter({code: 0 for code in CANONICAL_FAILURE_CODES})
    support: dict[str, set[str]] = {code: set() for code in CANONICAL_FAILURE_CODES}
    source_hashes: list[str] = []
    episode_ids: list[int | str] = []
    seen_hashes: set[str] = set()
    for path in args.replays:
        source_hash = file_sha256(path)
        if source_hash in seen_hashes:
            raise SystemExit(f"duplicate replay bytes in corpus: {path}")
        seen_hashes.add(source_hash)
        audit = audit_episode(path, args.agent_name)
        if str(audit.episode_id) in {str(value) for value in episode_ids}:
            raise SystemExit(f"duplicate episode id in corpus: {audit.episode_id}")
        audits.append(audit)
        source_hashes.append(source_hash)
        episode_ids.append(audit.episode_id)
        counts.update(audit.metadata.get("finding_counts", {}))
        canonical.update(audit.metadata.get("canonical_failure_counts", {}))
        for code, mode in audit.metadata.get("classifier_support", {}).items():
            support.setdefault(code, set()).add(str(mode))
        (args.out_dir / f"{audit.episode_id}.json").write_text(
            json.dumps(audit.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    overall = sum(value.overall_score for value in audits) / len(audits) if audits else 0.0
    summary = {
        "candidate_bundle_sha256": args.candidate_sha256,
        "corpus_id": args.corpus_id,
        "corpus_kind": args.corpus_kind,
        "episodes": len(audits),
        "episode_ids": episode_ids,
        "source_sha256": source_hashes,
        "wins": sum(value.result == "WIN" for value in audits),
        "losses": sum(value.result == "LOSS" for value in audits),
        "mean_overall_score": overall,
        "finding_counts": dict(counts),
        "canonical_failure_counts": {code: canonical[code] for code in CANONICAL_FAILURE_CODES},
        "classifier_support": {code: sorted(values) for code, values in support.items()},
        "fatal": sum(f.severity == "FATAL" for a in audits for f in a.findings),
        "major": sum(f.severity == "MAJOR" for a in audits for f in a.findings),
        "minor": sum(f.severity == "MINOR" for a in audits for f in a.findings),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

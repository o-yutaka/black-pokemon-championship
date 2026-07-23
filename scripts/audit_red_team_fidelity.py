from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from red_team.replay_grounded_agent import ReplayGroundedPolicy, read_deck


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure reconstructed Red Team action fidelity against source official replays.")
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--out", default=ROOT / "artifacts" / "red_team_fidelity.json", type=Path)
    parser.add_argument("--minimum-overall", type=float, default=0.35)
    parser.add_argument("--minimum-attack", type=float, default=0.95)
    args = parser.parse_args()
    profiles = json.loads((ROOT / "red_team" / "profiles.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "red_team" / "replay_sources.json").read_text(encoding="utf-8"))
    report = {"verdict": "PASS", "evidence_identity": "REPLAY_GROUNDED_RECONSTRUCTION", "matchups": {}, "skipped": {}}
    for slug, source in sources.items():
        if source.get("source_type") != "official_replay":
            report["skipped"][slug] = {
                "reason": "fidelity requires an exact official-replay deck/policy identity",
                "source": source,
            }
            continue
        replay_path = args.replay_dir / source["filename"]
        if not replay_path.is_file():
            report["verdict"] = "HOLD"
            report["matchups"][slug] = {"passed": False, "error": f"missing replay {replay_path}"}
            continue
        actual_sha = sha256(replay_path)
        expected_sha = source.get("sha256")
        if actual_sha != expected_sha:
            report["verdict"] = "HOLD"
            report["matchups"][slug] = {
                "passed": False,
                "error": "official replay hash mismatch",
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
            }
            continue
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
        seat = int(source["seat"])
        policy = ReplayGroundedPolicy(read_deck(ROOT / "red_team" / "decks" / f"{slug}.csv"), profiles[slug])
        total = matched = attacks = attacks_matched = 0
        steps = payload.get("steps") or []
        for index, pair in enumerate(steps[:-1]):
            if not isinstance(pair, list) or seat >= len(pair) or not isinstance(pair[seat], dict):
                continue
            row = pair[seat]
            if row.get("status") != "ACTIVE":
                continue
            obs = row.get("observation") if isinstance(row.get("observation"), dict) else None
            if not isinstance(obs, dict) or not isinstance(obs.get("select"), dict) or not (obs["select"].get("option") or []):
                continue
            next_pair = steps[index + 1]
            actual = next_pair[seat].get("action") if isinstance(next_pair, list) and seat < len(next_pair) and isinstance(next_pair[seat], dict) else None
            if not isinstance(actual, list):
                continue
            predicted = policy.agent(obs)
            total += 1
            matched += actual == predicted
            options = obs["select"]["option"]
            recorded_attack = any(type(value) is int and 0 <= value < len(options) and isinstance(options[value], dict) and options[value].get("type") == 13 for value in actual)
            if recorded_attack:
                attacks += 1
                attacks_matched += actual == predicted
        overall = matched / total if total else 0.0
        attack = attacks_matched / attacks if attacks else 1.0
        passed = overall >= args.minimum_overall and attack >= args.minimum_attack
        if not passed:
            report["verdict"] = "HOLD"
        report["matchups"][slug] = {
            "episode_id": source["episode_id"],
            "replay_sha256": actual_sha,
            "decisions": total,
            "matches": matched,
            "overall_fidelity": overall,
            "attack_decisions": attacks,
            "attack_matches": attacks_matched,
            "attack_fidelity": attack,
            "passed": passed,
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

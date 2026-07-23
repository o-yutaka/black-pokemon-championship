from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.evaluation.loss_miner import LOSS_MODES, aggregate_reports, mine_episode


def _markdown(summary: dict) -> str:
    lines = [
        "# BLACK Replay Repair Queue",
        "",
        f"- Episodes: **{summary['episodes']}**",
        f"- Losses: **{summary['losses']}**",
        f"- Cases: **{summary['total_cases']}**",
        "",
        "| Priority | Loss mode | Cases | Episodes | Policy hook |",
        "|---:|---|---:|---:|---|",
    ]
    for item in summary["repair_queue"]:
        lines.append(
            f"| {item['priority']} | `{item['loss_mode']}` | {item['count']} | "
            f"{len(item['episodes'])} | `{item['policy_hook']}` |"
        )
    lines.extend(["", "## Acceptance contracts", ""])
    for item in summary["repair_queue"]:
        lines.append(f"### {item['loss_mode']}")
        lines.append(item["acceptance"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine five championship loss modes from official CABT replay JSON files."
    )
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--agent-name", default="ジェニファー")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "artifacts" / "loss_mining",
    )
    parser.add_argument(
        "--fail-on-fatal",
        action="store_true",
        help="Return non-zero when any mined case has FATAL severity.",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    fatal = 0
    for path in args.replays:
        report = mine_episode(path, args.agent_name)
        reports.append(report)
        payload = report.to_dict()
        fatal += sum(case["severity"] == "FATAL" for case in payload["cases"])
        (args.out_dir / f"{report.episode_id}.loss_modes.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = aggregate_reports(reports)
    summary["fatal"] = fatal
    summary["supported_loss_modes"] = list(LOSS_MODES)
    (args.out_dir / "repair_queue.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.out_dir / "REPAIR_QUEUE.md").write_text(_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_fatal and fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())

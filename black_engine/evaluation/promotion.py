from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GateCheck:
    name: str
    passed: bool
    actual: Any
    required: Any


@dataclass
class PromotionVerdict:
    verdict: str
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(value.passed for value in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "passed": self.passed,
            "checks": [value.__dict__ for value in self.checks],
        }


def _runtime_checks(runtime: dict, minimum_completed: int) -> list[GateCheck]:
    completed = int(runtime.get("completed", 0))
    checks = [GateCheck("games_completed", completed >= minimum_completed, completed, minimum_completed)]
    for key in (
        "crash",
        "runtime_error",
        "illegal_action",
        "mandatory_empty",
        "timeout",
        "fallback",
        "search_resource_leak",
    ):
        actual = int(runtime.get(key, 0))
        checks.append(GateCheck(key, actual == 0, actual, 0))
    return checks


def _required_matchups(manifest: dict) -> list[str]:
    promotion = manifest.get("promotion") if isinstance(manifest.get("promotion"), dict) else {}
    matchups = manifest.get("matchups") if isinstance(manifest.get("matchups"), dict) else {}
    explicit = promotion.get("required_matchups")
    if isinstance(explicit, list) and all(isinstance(value, str) for value in explicit):
        return list(dict.fromkeys(explicit))
    selected = [slug for slug, config in matchups.items() if config.get("required_for_promotion") is True]
    return selected or list(matchups)


def _replay_checks(manifest: dict, replay_summary: dict | None) -> list[GateCheck]:
    promotion = manifest.get("promotion") if isinstance(manifest.get("promotion"), dict) else {}
    required = promotion.get("required_replay_taxonomy")
    if not isinstance(required, list) or not required:
        return []
    checks = [GateCheck("postfix_replay.present", isinstance(replay_summary, dict), bool(replay_summary), True)]
    if not isinstance(replay_summary, dict):
        return checks
    episodes = int(replay_summary.get("episodes", 0))
    minimum = int(promotion.get("minimum_postfix_replay_episodes", 1))
    checks.append(GateCheck("postfix_replay.episodes", episodes >= minimum, episodes, minimum))
    if promotion.get("require_zero_fatal_replay_findings", True):
        fatal = int(replay_summary.get("fatal", 0))
        checks.append(GateCheck("postfix_replay.fatal", fatal == 0, fatal, 0))
    counts = replay_summary.get("canonical_failure_counts") if isinstance(replay_summary.get("canonical_failure_counts"), dict) else {}
    support = replay_summary.get("classifier_support") if isinstance(replay_summary.get("classifier_support"), dict) else {}
    for code in required:
        checks.append(GateCheck(f"postfix_replay.{code}.supported", bool(support.get(code)), support.get(code), "non-empty"))
        actual = int(counts.get(code, 0))
        checks.append(GateCheck(f"postfix_replay.{code}.count", actual == 0, actual, 0))
    return checks


def evaluate_promotion(manifest: dict, summaries: dict[str, dict], replay_summary: dict | None = None) -> PromotionVerdict:
    promotion = manifest.get("promotion") if isinstance(manifest.get("promotion"), dict) else {}
    matchups = manifest.get("matchups") if isinstance(manifest.get("matchups"), dict) else {}
    required_slugs = _required_matchups(manifest)
    checks: list[GateCheck] = [
        GateCheck("required_matchup_count", len(required_slugs) > 0, len(required_slugs), ">0")
    ]
    total_runtime = {
        key: 0
        for key in (
            "completed",
            "crash",
            "runtime_error",
            "illegal_action",
            "mandatory_empty",
            "timeout",
            "fallback",
            "search_resource_leak",
        )
    }
    for slug in required_slugs:
        config = matchups.get(slug)
        checks.append(GateCheck(f"{slug}.configured", isinstance(config, dict), bool(config), True))
        if not isinstance(config, dict):
            continue
        summary = summaries.get(slug)
        checks.append(GateCheck(f"{slug}.present", summary is not None, bool(summary), True))
        if summary is None:
            continue
        games = int(summary.get("games", 0))
        seat0 = int(summary.get("seat0_games", 0))
        seat1 = int(summary.get("seat1_games", 0))
        required_games = int(config.get("minimum_games", promotion.get("minimum_games_per_matchup", 200)))
        required_seat = required_games // 2
        checks.extend(
            [
                GateCheck(f"{slug}.games", games == required_games, games, required_games),
                GateCheck(f"{slug}.seat0", seat0 == required_seat, seat0, required_seat),
                GateCheck(f"{slug}.seat1", seat1 == required_seat, seat1, required_seat),
                GateCheck(
                    f"{slug}.win_rate",
                    float(summary.get("win_rate", 0.0)) >= float(config.get("minimum_win_rate", 0.5)),
                    float(summary.get("win_rate", 0.0)),
                    float(config.get("minimum_win_rate", 0.5)),
                ),
                GateCheck(
                    f"{slug}.wilson_low",
                    float(summary.get("wilson_low", 0.0)) >= float(config.get("minimum_wilson_low", 0.4)),
                    float(summary.get("wilson_low", 0.0)),
                    float(config.get("minimum_wilson_low", 0.4)),
                ),
                GateCheck(
                    f"{slug}.evidence_mode",
                    summary.get("evidence_mode") == "PROMOTION",
                    summary.get("evidence_mode"),
                    "PROMOTION",
                ),
            ]
        )
        runtime = summary.get("runtime") if isinstance(summary.get("runtime"), dict) else {}
        for key in total_runtime:
            total_runtime[key] += int(runtime.get(key, 0))
    checks.extend(_runtime_checks(total_runtime, int(promotion.get("minimum_runtime_completed", 400))))
    checks.extend(_replay_checks(manifest, replay_summary))
    return PromotionVerdict("PROMOTE" if all(value.passed for value in checks) else "HOLD", checks)


def load_summaries(root: str | Path) -> dict[str, dict]:
    base = Path(root)
    summaries: dict[str, dict] = {}
    for path in base.glob("*/summary.json"):
        summaries[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    return summaries

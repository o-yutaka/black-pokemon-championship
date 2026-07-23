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
        return {"verdict": self.verdict, "passed": self.passed, "checks": [value.__dict__ for value in self.checks]}


def _runtime_checks(runtime: dict, minimum_completed: int) -> list[GateCheck]:
    completed = int(runtime.get("completed", 0))
    checks = [GateCheck("games_completed", completed >= minimum_completed, completed, minimum_completed)]
    for key in ("crash", "runtime_error", "illegal_action", "mandatory_empty", "timeout", "fallback", "search_resource_leak"):
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

    expected_candidate = str(promotion.get("candidate_bundle_sha256", ""))
    replay_candidate = str(replay_summary.get("candidate_bundle_sha256", ""))
    required_kind = str(promotion.get("required_replay_corpus_kind", "POST_FIX_HOLDOUT"))
    corpus_kind = str(replay_summary.get("corpus_kind", ""))
    source_hashes = replay_summary.get("source_sha256") if isinstance(replay_summary.get("source_sha256"), list) else []
    episode_ids = replay_summary.get("episode_ids") if isinstance(replay_summary.get("episode_ids"), list) else []
    corpus_id = str(replay_summary.get("corpus_id", ""))
    episodes = int(replay_summary.get("episodes", 0))
    minimum = int(promotion.get("minimum_postfix_replay_episodes", 1))

    checks.extend(
        [
            GateCheck(
                "postfix_replay.candidate_sha",
                bool(expected_candidate)
                and expected_candidate != "REQUIRED_BEFORE_RUN"
                and replay_candidate == expected_candidate,
                replay_candidate,
                expected_candidate,
            ),
            GateCheck("postfix_replay.corpus_kind", corpus_kind == required_kind, corpus_kind, required_kind),
            GateCheck("postfix_replay.corpus_id", bool(corpus_id), corpus_id, "non-empty"),
            GateCheck("postfix_replay.episodes", episodes >= minimum, episodes, minimum),
            GateCheck("postfix_replay.source_hashes", len(source_hashes) == episodes and all(isinstance(value, str) and len(value) == 64 for value in source_hashes), len(source_hashes), episodes),
            GateCheck("postfix_replay.unique_sources", len(set(source_hashes)) == episodes, len(set(source_hashes)), episodes),
            GateCheck("postfix_replay.unique_episode_ids", len(episode_ids) == episodes and len(set(map(str, episode_ids))) == episodes, len(set(map(str, episode_ids))), episodes),
        ]
    )
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
    checks: list[GateCheck] = [GateCheck("required_matchup_count", len(required_slugs) > 0, len(required_slugs), ">0")]
    candidate_hashes: set[str] = set()
    engine_hashes: set[str] = set()
    total_runtime = {key: 0 for key in ("completed", "crash", "runtime_error", "illegal_action", "mandatory_empty", "timeout", "fallback", "search_resource_leak")}

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
        candidate_sha = str(summary.get("candidate_bundle_sha256", ""))
        opponent_sha = str(summary.get("opponent_bundle_sha256", ""))
        engine_sha = str(summary.get("engine_sha256", ""))
        expected_opponent_sha = str(config.get("bundle_sha256", ""))
        if candidate_sha:
            candidate_hashes.add(candidate_sha)
        if engine_sha:
            engine_hashes.add(engine_sha)
        checks.extend(
            [
                GateCheck(f"{slug}.matchup_identity", summary.get("matchup") == slug, summary.get("matchup"), slug),
                GateCheck(f"{slug}.candidate_sha_present", bool(candidate_sha), candidate_sha, "non-empty"),
                GateCheck(f"{slug}.engine_sha_present", bool(engine_sha), engine_sha, "non-empty"),
                GateCheck(
                    f"{slug}.opponent_sha",
                    bool(expected_opponent_sha) and expected_opponent_sha != "REQUIRED_BEFORE_RUN" and opponent_sha == expected_opponent_sha,
                    opponent_sha,
                    expected_opponent_sha,
                ),
                GateCheck(f"{slug}.games", games == required_games, games, required_games),
                GateCheck(f"{slug}.seat0", seat0 == required_seat, seat0, required_seat),
                GateCheck(f"{slug}.seat1", seat1 == required_seat, seat1, required_seat),
                GateCheck(f"{slug}.win_rate", float(summary.get("win_rate", 0.0)) >= float(config.get("minimum_win_rate", 0.5)), float(summary.get("win_rate", 0.0)), float(config.get("minimum_win_rate", 0.5))),
                GateCheck(f"{slug}.wilson_low", float(summary.get("wilson_low", 0.0)) >= float(config.get("minimum_wilson_low", 0.4)), float(summary.get("wilson_low", 0.0)), float(config.get("minimum_wilson_low", 0.4))),
                GateCheck(f"{slug}.evidence_mode", summary.get("evidence_mode") == "PROMOTION", summary.get("evidence_mode"), "PROMOTION"),
            ]
        )
        runtime = summary.get("runtime") if isinstance(summary.get("runtime"), dict) else {}
        for key in total_runtime:
            total_runtime[key] += int(runtime.get(key, 0))

    expected_candidate = str(promotion.get("candidate_bundle_sha256", ""))
    expected_engine = str(promotion.get("engine_sha256", ""))
    checks.extend(
        [
            GateCheck("candidate_sha_consistent", len(candidate_hashes) == 1, sorted(candidate_hashes), "one exact SHA"),
            GateCheck("engine_sha_consistent", len(engine_hashes) == 1, sorted(engine_hashes), "one exact SHA"),
            GateCheck(
                "candidate_sha_frozen",
                bool(expected_candidate) and expected_candidate != "REQUIRED_BEFORE_RUN" and candidate_hashes == {expected_candidate},
                sorted(candidate_hashes),
                expected_candidate,
            ),
            GateCheck(
                "engine_sha_frozen",
                bool(expected_engine) and expected_engine != "REQUIRED_BEFORE_RUN" and engine_hashes == {expected_engine},
                sorted(engine_hashes),
                expected_engine,
            ),
        ]
    )
    checks.extend(_runtime_checks(total_runtime, int(promotion.get("minimum_runtime_completed", 400))))
    checks.extend(_replay_checks(manifest, replay_summary))
    return PromotionVerdict("PROMOTE" if all(value.passed for value in checks) else "HOLD", checks)


def load_summaries(root: str | Path) -> dict[str, dict]:
    base = Path(root)
    summaries: dict[str, dict] = {}
    for path in base.glob("*/summary.json"):
        summaries[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    return summaries

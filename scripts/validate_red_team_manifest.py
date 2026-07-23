from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "red_team" / "manifest.json").read_text(encoding="utf-8"))
profiles = json.loads((ROOT / "red_team" / "profiles.json").read_text(encoding="utf-8"))
sources = json.loads((ROOT / "red_team" / "replay_sources.json").read_text(encoding="utf-8"))
promotion_sources = json.loads((ROOT / "red_team" / "promotion_sources.json").read_text(encoding="utf-8"))
training_path = ROOT / "red_team" / "training_replay_corpus.json"
training = json.loads(training_path.read_text(encoding="utf-8"))
matchups = payload.get("matchups") if isinstance(payload.get("matchups"), dict) else {}
promotion = payload.get("promotion") if isinstance(payload.get("promotion"), dict) else {}

required = {
    "crustle_ogerpon",
    "cynthia_garchomp",
    "grimmsnarl",
    "dragapult_cinderace",
    "mewtwo_mirror",
}
expected_promotion_sources = {"dragapult_cinderace", "mewtwo_mirror"}
configured_required = set(promotion.get("required_matchups") or [])
missing = sorted(required.difference(matchups))
if missing:
    raise SystemExit(f"missing core Red Team matchups: {missing}")
if configured_required != required:
    raise SystemExit(
        "promotion.required_matchups must be the exact five-deck core pool: "
        f"expected={sorted(required)}, actual={sorted(configured_required)}"
    )
if set(matchups) != set(profiles) or set(matchups) != set(sources):
    raise SystemExit(
        "manifest, profiles, and replay_sources must have identical matchup sets: "
        f"manifest={sorted(matchups)}, profiles={sorted(profiles)}, sources={sorted(sources)}"
    )
if set(promotion_sources) != expected_promotion_sources:
    raise SystemExit(
        "promotion_sources must currently freeze only the two independently executable challengers: "
        f"expected={sorted(expected_promotion_sources)}, actual={sorted(promotion_sources)}"
    )
if payload.get("evidence_law", {}).get("seat_balance") is not True:
    raise SystemExit("seat_balance must be true")
if payload.get("evidence_law", {}).get("search_api") != "absent from current production bundle; enforced by static gate":
    raise SystemExit("current production Search API absence must be explicit")
if int(promotion.get("minimum_runtime_completed", 0)) < 1000:
    raise SystemExit("minimum_runtime_completed must cover five matchups x 200 games")
if int(promotion.get("minimum_postfix_replay_episodes", 0)) <= 0:
    raise SystemExit("minimum_postfix_replay_episodes must be positive")
if promotion.get("required_replay_corpus_kind") != "POST_FIX_HOLDOUT":
    raise SystemExit("required_replay_corpus_kind must be POST_FIX_HOLDOUT")
training_corpus_sha = hashlib.sha256(training_path.read_bytes()).hexdigest()
if promotion.get("training_corpus_sha256") != training_corpus_sha:
    raise SystemExit(
        "promotion.training_corpus_sha256 must equal the exact frozen training corpus bytes: "
        f"expected={training_corpus_sha} actual={promotion.get('training_corpus_sha256')}"
    )
for field in ("candidate_bundle_sha256", "engine_sha256"):
    value = promotion.get(field)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"promotion.{field} must exist; use REQUIRED_BEFORE_RUN until locked")
    if value != "REQUIRED_BEFORE_RUN" and (len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower())):
        raise SystemExit(f"promotion.{field} must be REQUIRED_BEFORE_RUN or SHA-256")

training_rows = training.get("episodes") if isinstance(training.get("episodes"), list) else []
training_ids = [str(row.get("episode_id")) for row in training_rows if isinstance(row, dict)]
training_hashes = [str(row.get("sha256")) for row in training_rows if isinstance(row, dict)]
if len(training_rows) != 14 or len(set(training_ids)) != 14 or len(set(training_hashes)) != 14:
    raise SystemExit("training replay corpus must freeze 14 unique episode IDs and hashes")
if any(len(value) != 64 for value in training_hashes):
    raise SystemExit("training replay corpus hashes must be SHA-256")

for slug, config in matchups.items():
    for field in (
        "bundle_path",
        "bundle_sha256",
        "policy_source",
        "strength_evidence",
        "required_for_promotion",
        "minimum_games",
        "minimum_win_rate",
        "minimum_wilson_low",
    ):
        if field not in config:
            raise SystemExit(f"{slug}: missing {field}")
    if config["strength_evidence"] not in {"PROMOTION", "STRESS_ONLY"}:
        raise SystemExit(f"{slug}: invalid strength_evidence={config['strength_evidence']!r}")
    spec = promotion_sources.get(slug)
    if spec is not None:
        if config["strength_evidence"] != "PROMOTION":
            raise SystemExit(f"{slug}: frozen executable challenger must be PROMOTION eligible")
        if config.get("promotion_source") != spec:
            raise SystemExit(f"{slug}: manifest promotion_source must equal promotion_sources.json")
        if spec.get("source_type") != "git_submission_commit":
            raise SystemExit(f"{slug}: promotion source must use git_submission_commit")
        commit = str(spec.get("commit_sha", ""))
        if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit.lower()):
            raise SystemExit(f"{slug}: invalid frozen commit SHA")
        builder = PurePosixPath(str(spec.get("builder_path", "")))
        if not builder.parts or builder.is_absolute() or ".." in builder.parts:
            raise SystemExit(f"{slug}: unsafe builder_path")
        if spec.get("evidence_identity") != "FROZEN_BLACK_EXECUTABLE_BUNDLE":
            raise SystemExit(f"{slug}: invalid executable evidence identity")
    elif config["strength_evidence"] != "STRESS_ONLY":
        raise SystemExit(f"{slug}: no frozen executable source; must remain STRESS_ONLY")

    if int(config["minimum_games"]) <= 0 or int(config["minimum_games"]) % 2:
        raise SystemExit(f"{slug}: minimum_games must be positive and even")
    if slug in required and config["required_for_promotion"] is not True:
        raise SystemExit(f"{slug}: core matchup must be required_for_promotion=true")
    deck_path = ROOT / "red_team" / "decks" / f"{slug}.csv"
    if not deck_path.is_file():
        raise SystemExit(f"{slug}: missing source deck {deck_path}")
    deck = [line.strip() for line in deck_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(deck) != 60 or any(not value.isdigit() for value in deck):
        raise SystemExit(f"{slug}: source deck must contain exactly 60 integer IDs")
    source = sources[slug]
    source_type = source.get("source_type")
    if source_type not in {
        "official_replay",
        "official_replay_and_frozen_black_candidate",
        "frozen_black_candidate",
    }:
        raise SystemExit(f"{slug}: invalid source_type={source_type!r}")
    if source_type == "official_replay":
        if not source.get("filename") or not source.get("episode_id") or not source.get("sha256"):
            raise SystemExit(f"{slug}: exact official replay source requires filename, episode_id, and sha256")
        if spec is None and config["strength_evidence"] != "STRESS_ONLY":
            raise SystemExit(f"{slug}: replay-only reconstruction cannot be PROMOTION strength evidence")
    if source_type == "frozen_black_candidate" and not source.get("deck_blob_sha"):
        raise SystemExit(f"{slug}: frozen candidate source requires deck_blob_sha")
    if source_type == "official_replay_and_frozen_black_candidate":
        if not source.get("sha256") or not source.get("deck_blob_sha"):
            raise SystemExit(f"{slug}: combined source requires replay sha256 and deck_blob_sha")
    policy_source = str(config.get("policy_source", "")).lower()
    forbidden_official_claims = ("official ladder", "official replay reconstruction")
    if source_type == "frozen_black_candidate" and any(token in policy_source for token in forbidden_official_claims):
        raise SystemExit(f"{slug}: frozen candidate must not be described as official replay reconstruction")

required_taxonomy = {
    "LETHAL_MISS",
    "BAD_SPREAD_TARGET",
    "ENERGY_ATTACH_ERROR",
    "TERMINAL_MISS",
    "PROMOTION_ERROR",
}
actual_taxonomy = set(promotion.get("required_replay_taxonomy") or [])
if actual_taxonomy != required_taxonomy:
    raise SystemExit(
        "required_replay_taxonomy mismatch: "
        f"expected={sorted(required_taxonomy)}, actual={sorted(actual_taxonomy)}"
    )
applicability = promotion.get("replay_taxonomy_applicability")
if not isinstance(applicability, dict) or set(applicability) != required_taxonomy:
    raise SystemExit("replay_taxonomy_applicability must cover the exact canonical taxonomy")
if applicability.get("BAD_SPREAD_TARGET") != "NOT_APPLICABLE_ROCKET_MEWTWO_FIXED_DECK_HAS_NO_SPREAD_TARGET_ACTION":
    raise SystemExit("Rocket Mewtwo BAD_SPREAD_TARGET must be explicit N/A, never fake observed support")
if any(applicability.get(code) != "REQUIRED" for code in required_taxonomy - {"BAD_SPREAD_TARGET"}):
    raise SystemExit("all non-spread canonical replay classifiers must remain REQUIRED")
print("RED_TEAM_MANIFEST PASS")

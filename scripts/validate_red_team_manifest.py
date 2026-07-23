from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "red_team" / "manifest.json").read_text(encoding="utf-8"))
profiles = json.loads((ROOT / "red_team" / "profiles.json").read_text(encoding="utf-8"))
sources = json.loads((ROOT / "red_team" / "replay_sources.json").read_text(encoding="utf-8"))
matchups = payload.get("matchups") if isinstance(payload.get("matchups"), dict) else {}
promotion = payload.get("promotion") if isinstance(payload.get("promotion"), dict) else {}

required = {
    "crustle_ogerpon",
    "cynthia_garchomp",
    "grimmsnarl",
    "dragapult_cinderace",
    "mewtwo_mirror",
}
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
if payload.get("evidence_law", {}).get("seat_balance") is not True:
    raise SystemExit("seat_balance must be true")
if int(promotion.get("minimum_runtime_completed", 0)) < 1000:
    raise SystemExit("minimum_runtime_completed must cover five matchups x 200 games")
if int(promotion.get("minimum_postfix_replay_episodes", 0)) <= 0:
    raise SystemExit("minimum_postfix_replay_episodes must be positive")

for slug, config in matchups.items():
    for field in (
        "bundle_path",
        "bundle_sha256",
        "policy_source",
        "required_for_promotion",
        "minimum_games",
        "minimum_win_rate",
        "minimum_wilson_low",
    ):
        if field not in config:
            raise SystemExit(f"{slug}: missing {field}")
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
print("RED_TEAM_MANIFEST PASS")

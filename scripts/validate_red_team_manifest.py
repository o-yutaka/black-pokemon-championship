from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "red_team" / "manifest.json"
payload = json.loads(path.read_text(encoding="utf-8"))
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
if payload.get("evidence_law", {}).get("seat_balance") is not True:
    raise SystemExit("seat_balance must be true")
if int(promotion.get("minimum_runtime_completed", 0)) < 1000:
    raise SystemExit("minimum_runtime_completed must cover five matchups x 200 games")

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

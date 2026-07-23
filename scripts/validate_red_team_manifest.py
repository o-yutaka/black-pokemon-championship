from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "red_team" / "manifest.json"
payload = json.loads(path.read_text(encoding="utf-8"))
required = {"grimmsnarl", "crustle_ogerpon", "mega_starmie_cinderace", "alakazam", "mega_abomasnow", "mewtwo_mirror"}
matchups = payload.get("matchups") if isinstance(payload.get("matchups"), dict) else {}
missing = sorted(required.difference(matchups))
if missing:
    raise SystemExit(f"missing Red Team matchups: {missing}")
if payload.get("evidence_law", {}).get("seat_balance") is not True:
    raise SystemExit("seat_balance must be true")
for slug, config in matchups.items():
    for field in ("bundle_path", "bundle_sha256", "policy_source", "minimum_games", "minimum_win_rate", "minimum_wilson_low"):
        if field not in config:
            raise SystemExit(f"{slug}: missing {field}")
    if int(config["minimum_games"]) <= 0 or int(config["minimum_games"]) % 2:
        raise SystemExit(f"{slug}: minimum_games must be positive and even")
print("RED_TEAM_MANIFEST PASS")

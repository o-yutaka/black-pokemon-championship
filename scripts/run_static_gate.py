from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from black_engine.factory import CANDIDATE, SUPPORTED_CANDIDATES, build_candidate_base_policy
from submission_contract import validate_deck_file, validate_source_layout

FORBIDDEN = ("mewtwo_spidops", "garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam")


def main() -> int:
    source_report = validate_source_layout(ROOT)
    deck_report = validate_deck_file(ROOT / "deck.csv")
    if CANDIDATE != "dragapult_cinderace" or SUPPORTED_CANDIDATES != (CANDIDATE,):
        raise SystemExit("production factory is not single-deck Dragapult")
    policy = build_candidate_base_policy(CANDIDATE)
    if policy.__class__.__name__ != "DragapultChampionshipPolicy":
        raise SystemExit("wrong production policy")
    main_text = (ROOT / "main.py").read_text(encoding="utf-8")
    ast.parse(main_text)
    for token in FORBIDDEN:
        if token in main_text:
            raise SystemExit(f"forbidden candidate in root main.py: {token}")
    if (ROOT / "candidates").exists():
        raise SystemExit("cleanroom repository must not contain candidates/")
    report = {
        "verdict": "DRAGAPULT_CLEANROOM_STATIC_PASS",
        "candidate": CANDIDATE,
        "deck_total": deck_report["total"],
        "source": source_report,
        "other_candidates": "ABSENT",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

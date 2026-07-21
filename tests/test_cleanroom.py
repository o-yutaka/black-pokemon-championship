from pathlib import Path

import pytest

from black_engine.factory import CANDIDATE, SUPPORTED_CANDIDATES, build_candidate_base_policy
from submission_contract import validate_deck_file, validate_source_layout

ROOT = Path(__file__).resolve().parents[1]


def test_cleanroom_is_dragapult_only():
    assert CANDIDATE == "dragapult_cinderace"
    assert SUPPORTED_CANDIDATES == (CANDIDATE,)
    assert build_candidate_base_policy(CANDIDATE).__class__.__name__ == "DragapultChampionshipPolicy"


@pytest.mark.parametrize("name", ["mewtwo_spidops", "garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam"])
def test_other_production_candidates_are_impossible(name):
    with pytest.raises(ValueError, match="single-deck branch locked"):
        build_candidate_base_policy(name)


def test_root_is_complete_submission_source():
    report = validate_source_layout(ROOT)
    assert report["candidate"] == CANDIDATE
    assert report["deck_total"] == 60
    assert validate_deck_file(ROOT / "deck.csv")["total"] == 60


def test_repository_contains_no_other_candidate_directory():
    candidates = ROOT / "candidates"
    assert not candidates.exists()


def test_root_entrypoint_cannot_name_other_deck():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    for forbidden in ("mewtwo_spidops", "garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam"):
        assert forbidden not in source

from pathlib import Path

import pytest

from black_engine.factory import CANDIDATE, SUPPORTED_CANDIDATES, build_candidate_base_policy

ROOT = Path(__file__).resolve().parents[1]


def test_repository_is_locked_to_one_dragapult_candidate():
    assert CANDIDATE == "dragapult_cinderace"
    assert SUPPORTED_CANDIDATES == ("dragapult_cinderace",)
    assert build_candidate_base_policy(CANDIDATE).__class__.__name__ == "DragapultChampionshipPolicy"


@pytest.mark.parametrize(
    "forbidden",
    ["mewtwo_spidops", "garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam"],
)
def test_production_factory_rejects_every_other_deck(forbidden):
    with pytest.raises(ValueError, match="single-deck branch locked"):
        build_candidate_base_policy(forbidden)


def test_root_deck_is_exact_candidate_deck():
    root_deck = (ROOT / "deck.csv").read_bytes()
    candidate_deck = (ROOT / "candidates" / CANDIDATE / "deck.csv").read_bytes()
    assert root_deck == candidate_deck
    assert len([line for line in root_deck.decode().splitlines() if line.strip()]) == 60


def test_root_main_names_only_dragapult_candidate():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "dragapult_cinderace" in source or "CANDIDATE" in source
    for forbidden in ("mewtwo_spidops", "garchomp_spiritomb", "crustle_redteam", "grimmsnarl_redteam"):
        assert forbidden not in source

from collections import Counter
from pathlib import Path

from black_engine import read_deck, validate_deck
from submission_contract import validate_source_layout

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_DECK_COUNTS = Counter(
    {
        151: 1,
        666: 4,
        119: 4,
        120: 4,
        121: 3,
        131: 3,
        132: 2,
        133: 2,
        217: 2,
        2: 6,
        5: 7,
        1086: 4,
        1079: 3,
        1127: 2,
        1152: 1,
        1097: 2,
        1123: 1,
        1088: 1,
        1231: 3,
        1198: 2,
        1227: 2,
        1182: 1,
    }
)

POKEMON_IDS = {151, 666, 119, 120, 121, 131, 132, 133, 217}
ENERGY_IDS = {2, 5}
TRAINER_IDS = set(EXPECTED_DECK_COUNTS) - POKEMON_IDS - ENERGY_IDS


def test_only_final_dragapult_deck_is_present():
    deck = read_deck(ROOT / "deck.csv")
    counts = Counter(deck)
    report = validate_deck(deck, {1088})

    assert report["ok"]
    assert len(deck) == 60
    assert counts == EXPECTED_DECK_COUNTS
    assert sum(counts[cid] for cid in POKEMON_IDS) == 25
    assert sum(counts[cid] for cid in TRAINER_IDS) == 22
    assert sum(counts[cid] for cid in ENERGY_IDS) == 13
    assert counts[1088] == 1


def test_source_layout_is_dragapult_only():
    report = validate_source_layout(ROOT)
    assert report["candidate"] == "dragapult_cinderace"
    assert not (ROOT / "candidates").exists()

from collections import Counter
from pathlib import Path

from black_engine import read_deck, validate_deck
from submission_contract import validate_source_layout

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_DECK_COUNTS = Counter(
    {
        400: 4,
        401: 4,
        414: 2,
        431: 2,
        432: 1,
        463: 2,
        1094: 3,
        1097: 1,
        1119: 1,
        1134: 4,
        1152: 3,
        1159: 1,
        1197: 2,
        1216: 4,
        1217: 1,
        1218: 3,
        1220: 3,
        1227: 2,
        1257: 3,
        1: 7,
        3: 1,
        5: 2,
        15: 4,
    }
)

POKEMON_IDS = {400, 401, 414, 431, 432, 463}
ENERGY_IDS = {1, 3, 5, 15}
TRAINER_IDS = set(EXPECTED_DECK_COUNTS) - POKEMON_IDS - ENERGY_IDS


def test_only_final_rocket_mewtwo_xerosic2_deck_is_present():
    deck = read_deck(ROOT / "deck.csv")
    counts = Counter(deck)
    report = validate_deck(deck, {1159})

    assert report["ok"]
    assert len(deck) == 60
    assert counts == EXPECTED_DECK_COUNTS
    assert sum(counts[cid] for cid in POKEMON_IDS) == 16
    assert sum(counts[cid] for cid in TRAINER_IDS) == 30
    assert sum(counts[cid] for cid in ENERGY_IDS) == 14
    assert counts[1159] == 1
    assert counts[1197] == 2
    assert counts[1152] == 3
    assert counts[1175] == 0


def test_source_layout_is_rocket_mewtwo_only():
    report = validate_source_layout(ROOT)
    assert report["candidate"] == "rocket_mewtwo_xerosic2"
    assert not (ROOT / "candidates").exists()

from collections import Counter
from pathlib import Path

from black_engine import read_deck, validate_deck
from submission_contract import validate_source_layout

ROOT = Path(__file__).resolve().parents[1]


def test_only_final_dragapult_deck_is_present():
    deck = read_deck(ROOT / "deck.csv")
    counts = Counter(deck)
    assert validate_deck(deck, {1088})["ok"]
    assert len(deck) == 60
    assert (counts[119], counts[120], counts[121]) == (4, 4, 3)
    assert (counts[131], counts[132], counts[133]) == (3, 2, 2)
    assert counts[666] == 4 and counts[217] == 2
    assert counts[2] == 6 and counts[5] == 7


def test_source_layout_is_dragapult_only():
    report = validate_source_layout(ROOT)
    assert report["candidate"] == "dragapult_cinderace"
    assert not (ROOT / "candidates").exists()

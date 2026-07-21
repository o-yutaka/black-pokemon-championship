from collections import Counter
from pathlib import Path

from black_engine.dragapult_policy import DragapultCinderacePolicy
from black_engine.factory import build_hybrid_policy
from black_engine.guards import DragapultEnergyColorGuard, guards_for
from black_engine.official_observation import normalize_official_observation
from black_engine.planners import planners_for
from black_engine.truth import LegalOption, PlayerView, TruthState, build_truth_state
from black_lab import read_deck, validate_deck

ROOT = Path(__file__).resolve().parents[1]
DECK_PATH = ROOT / "candidates" / "dragapult_cinderace" / "deck.csv"


def test_dragapult_championship_deck_is_legal_and_exact():
    deck = read_deck(DECK_PATH)
    report = validate_deck(deck, {1088})
    counts = Counter(deck)
    assert report["ok"], report
    assert counts[666] == 4
    assert counts[121] == 4
    assert counts[133] == 2
    assert counts[217] == 2
    assert counts[1088] == 1
    assert counts[2] == 6
    assert counts[5] == 8


def test_official_hp_is_converted_to_damage_non_destructively():
    obs = {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {"active": [{"id": 121, "hp": 200, "maxHp": 320, "energyCards": []}], "bench": [], "hand": [], "handCount": 0, "discard": [], "prize": [], "deckCount": 40},
                {"active": [{"id": 121, "hp": 70, "maxHp": 320, "energyCards": []}], "bench": [], "handCount": 4, "discard": [], "prize": [], "deckCount": 40},
            ],
        },
        "select": {"type": 0, "context": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 14}]},
        "logs": [],
    }
    normalized = normalize_official_observation(obs)
    truth = build_truth_state(normalized)
    assert "damage" not in obs["current"]["players"][0]["active"][0]
    assert truth.me.active[0].damage == 120
    assert truth.me.active[0].remaining_hp == 200
    assert truth.opponent.active[0].damage == 250
    assert truth.opponent.active[0].remaining_hp == 70


def _empty_player(index: int) -> PlayerView:
    return PlayerView(
        index=index,
        active=(),
        bench=(),
        hand_ids=(),
        hand_count=0,
        discard_ids=(),
        prize_ids=(),
        deck_count=40,
        supporter_played=False,
        retreated=False,
        energy_attached=False,
    )


def _truth_with_option(option: LegalOption) -> TruthState:
    return TruthState(
        actor=0,
        turn=1,
        result=-1,
        players=(_empty_player(0), _empty_player(1)),
        options=(option,),
        min_count=1,
        max_count=1,
        select_type=0,
        select_context=0,
        logs=(),
        raw_observation={},
    )


def test_fire_energy_preserves_azelf_colorless_route_but_rejects_dusclops():
    guard = DragapultEnergyColorGuard()
    azelf = LegalOption(0, 8, 2, 217, -1, "", {})
    dusclops = LegalOption(0, 8, 2, 132, -1, "", {})
    azelf_vote = guard.evaluate(_truth_with_option(azelf), azelf)
    dusclops_vote = guard.evaluate(_truth_with_option(dusclops), dusclops)
    assert not azelf_vote.hard_reject
    assert azelf_vote.penalty > 0
    assert dusclops_vote.hard_reject


def test_dragapult_candidate_wires_all_hybrid_layers():
    deck = read_deck(DECK_PATH)
    base = DragapultCinderacePolicy()
    policy = build_hybrid_policy("dragapult_cinderace", base, root=ROOT, ismcts=None)
    policy.set_deck(deck)
    assert policy.agent({"select": None}) == deck
    assert len(guards_for("dragapult_cinderace")) >= 6
    assert len(planners_for("dragapult_cinderace")) == 4

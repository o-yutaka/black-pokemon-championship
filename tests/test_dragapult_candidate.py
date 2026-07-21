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
    assert len(deck) == 60
    assert counts[151] == 1
    assert counts[666] == 4
    assert (counts[119], counts[120], counts[121]) == (4, 3, 4)
    assert (counts[131], counts[132], counts[133]) == (3, 2, 2)
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


def _base_obs(*, select: dict, my_bench=None, opponent_active=None, opponent_bench=None, hand=None):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {
                    "active": [{"id": 666, "serial": 10, "hp": 140, "maxHp": 140, "energyCards": []}],
                    "bench": my_bench or [],
                    "hand": hand or [],
                    "discard": [],
                },
                {
                    "active": opponent_active or [{"id": 431, "serial": 20, "hp": 280, "maxHp": 280, "energyCards": []}],
                    "bench": opponent_bench or [],
                    "hand": [],
                    "discard": [],
                },
            ],
        },
        "select": select,
        "logs": [],
    }


def test_energy_scoring_is_per_individual_dragapult_not_active_colors():
    policy = DragapultCinderacePolicy()
    bench_values = [
        {"id": 121, "serial": 101, "hp": 320, "maxHp": 320, "energyCards": [{"id": 5}]},
        {"id": 121, "serial": 102, "hp": 320, "maxHp": 320, "energyCards": [{"id": 2}]},
    ]
    select = {
        "type": 8,
        "context": 0,
        "minCount": 1,
        "maxCount": 1,
        "option": [
            {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0, "playerIndex": 0},
            {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 1, "playerIndex": 0},
        ],
    }
    obs = _base_obs(select=select, my_bench=bench_values, hand=[{"id": 2}])
    ctx = policy.build_context(obs)
    assert policy.score_option(select["option"][0], ctx) > policy.score_option(select["option"][1], ctx)


def test_drakloak_effect_resolves_select_deck_and_prefers_dragapult():
    policy = DragapultCinderacePolicy()
    select = {
        "type": 0,
        "context": 0,
        "effect": {"id": 120, "serial": 77, "playerIndex": 0},
        "deck": [{"id": 1097}, {"id": 121}],
        "minCount": 1,
        "maxCount": 1,
        "option": [
            {"type": 0, "area": 1, "index": 0, "playerIndex": 0},
            {"type": 0, "area": 1, "index": 1, "playerIndex": 0},
        ],
    }
    obs = _base_obs(select=select)
    ctx = policy.build_context(obs)
    assert policy.choose_single(select["option"], ctx) == 1


def test_dusknoir_target_window_prefers_immediate_ko():
    policy = DragapultCinderacePolicy()
    select = {
        "type": 0,
        "context": 0,
        "effect": {"id": 133, "serial": 88, "playerIndex": 0},
        "minCount": 1,
        "maxCount": 1,
        "option": [
            {"type": 0, "area": 4, "index": 0, "playerIndex": 1},
            {"type": 0, "area": 5, "index": 0, "playerIndex": 1},
        ],
    }
    obs = _base_obs(
        select=select,
        opponent_active=[{"id": 431, "serial": 201, "hp": 250, "maxHp": 280, "energyCards": []}],
        opponent_bench=[{"id": 121, "serial": 202, "hp": 120, "maxHp": 320, "energyCards": []}],
    )
    ctx = policy.build_context(obs)
    assert policy.choose_single(select["option"], ctx) == 1


def test_dragapult_candidate_wires_all_hybrid_layers():
    deck = read_deck(DECK_PATH)
    base = DragapultCinderacePolicy()
    policy = build_hybrid_policy("dragapult_cinderace", base, root=ROOT, ismcts=None)
    policy.set_deck(deck)
    assert policy.agent({"select": None}) == deck
    assert len(guards_for("dragapult_cinderace")) >= 6
    assert len(planners_for("dragapult_cinderace")) == 4

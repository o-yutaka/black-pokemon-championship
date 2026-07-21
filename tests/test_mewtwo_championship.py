from __future__ import annotations

from black_engine.mewtwo_guards import RocketEnergyAttachmentGuard
from black_engine.mewtwo_policy import build_mewtwo_policy
from black_engine.official_observation import normalize_official_observation
from black_engine.rocket_ledger import build_rocket_ledger, energy_units
from black_engine.truth import build_truth_state


def pokemon(card_id, *, hp=100, max_hp=None, energy=(), damage=0):
    maximum = max_hp if max_hp is not None else hp + damage
    return {
        "id": card_id,
        "hp": hp,
        "maxHp": maximum,
        "energyCards": [{"id": value} for value in energy],
    }


def base_players():
    return [
        {
            "active": [pokemon(431, hp=280, energy=(15, 1))],
            "bench": [
                pokemon(401, hp=130, energy=(1,)),
                pokemon(400, hp=50),
                pokemon(463, hp=80),
            ],
            "hand": [],
            "handCount": 0,
            "discard": [{"id": 1}],
            "prize": [None] * 6,
            "deckCount": 46,
            "benchMax": 5,
        },
        {
            "active": [pokemon(700, hp=220)],
            "bench": [],
            "handCount": 0,
            "discard": [],
            "prize": [None] * 6,
            "deckCount": 53,
        },
    ]


def observation(select, *, players=None, turn=3):
    return {
        "current": {
            "yourIndex": 0,
            "turn": turn,
            "result": -1,
            "players": players or base_players(),
            "stadium": [],
        },
        "select": select,
        "logs": [],
    }


def test_team_rocket_energy_counts_as_two_units():
    assert energy_units((15, 1)) == (2, 3)
    assert energy_units((5, 1)) == (1, 2)


def test_rocket_ledger_recognizes_ready_mewtwo_and_minimum_tier():
    truth = build_truth_state(normalize_official_observation(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 13, "attackId": 608, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0}],
    })))
    ledger = build_rocket_ledger(truth)
    assert ledger.rocket_count == 4
    assert ledger.active_mewtwo_ready is True
    assert ledger.minimum_discard == 1
    assert ledger.exact_mewtwo_terminal is True
    assert ledger.bench_basic_energy_cards == 1
    assert ledger.bench_special_energy_cards == 0


def test_opening_active_prefers_murkrow_over_exposure_of_mewtwo():
    players = base_players()
    players[0]["active"] = []
    players[0]["bench"] = []
    players[0]["hand"] = [{"id": 431}, {"id": 463}, {"id": 400}]
    players[0]["handCount"] = 3
    policy = build_mewtwo_policy()
    result = policy.agent(observation({
        "context": 1,
        "minCount": 1,
        "maxCount": 1,
        "option": [
            {"type": 0, "area": 2, "index": 0, "playerIndex": 0},
            {"type": 0, "area": 2, "index": 1, "playerIndex": 0},
            {"type": 0, "area": 2, "index": 2, "playerIndex": 0},
        ],
    }, players=players, turn=0))
    assert result == [1]


def test_erasure_ball_discards_minimum_basic_not_team_rocket_energy():
    players = base_players()
    players[0]["energy"] = [{"id": 15}, {"id": 1}]
    policy = build_mewtwo_policy()
    result = policy.agent(observation({
        "context": 8,
        "minCount": 0,
        "maxCount": 2,
        "option": [
            {"type": 4, "area": 8, "index": 0, "playerIndex": 0},
            {"type": 4, "area": 8, "index": 1, "playerIndex": 0},
        ],
    }, players=players))
    assert result == [1]


def test_optional_setup_bench_stops_at_four_rocket_bodies():
    players = base_players()
    players[0]["active"] = [pokemon(463, hp=80)]
    players[0]["bench"] = [pokemon(400, hp=50)]
    players[0]["hand"] = [{"id": 431}, {"id": 400}, {"id": 414}, {"id": 432}]
    players[0]["handCount"] = 4
    policy = build_mewtwo_policy()
    result = policy.agent(observation({
        "context": 2,
        "minCount": 0,
        "maxCount": 4,
        "option": [
            {"type": 0, "area": 2, "index": 0, "playerIndex": 0},
            {"type": 0, "area": 2, "index": 1, "playerIndex": 0},
            {"type": 0, "area": 2, "index": 2, "playerIndex": 0},
            {"type": 0, "area": 2, "index": 3, "playerIndex": 0},
        ],
    }, players=players, turn=0))
    assert set(result) == {0, 1}
    assert len(result) == 2


def test_team_rocket_energy_guard_rejects_non_rocket_target():
    players = base_players()
    players[0]["bench"].append(pokemon(999, hp=100))
    players[0]["hand"] = [{"id": 15}]
    players[0]["handCount"] = 1
    truth = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{
            "type": 8,
            "area": 2,
            "index": 0,
            "playerIndex": 0,
            "inPlayArea": 5,
            "inPlayIndex": 3,
        }],
    }, players=players))
    vote = RocketEnergyAttachmentGuard().evaluate(truth, truth.options[0])
    assert vote.hard_reject is True

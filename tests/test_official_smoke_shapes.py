from black_engine.official_observation import normalize_official_observation
from black_engine.truth import build_truth_state
from scripts.run_official_smoke import (
    classify_mewtwo_shape,
    effect_shape,
    oracle_bank_payload,
    pairings,
)


def _base_observation(select):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {
                    "active": [
                        {
                            "id": 431,
                            "serial": 9,
                            "playerIndex": 0,
                            "hp": 280,
                            "maxHp": 280,
                            "energyCards": [5, 5, 15],
                            "tools": [],
                            "preEvolution": [],
                        }
                    ],
                    "bench": [],
                    "hand": [],
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 47,
                },
                {
                    "active": [
                        {
                            "id": 381,
                            "serial": 20,
                            "playerIndex": 1,
                            "hp": 220,
                            "maxHp": 280,
                            "energyCards": [],
                            "tools": [],
                            "preEvolution": [],
                        }
                    ],
                    "bench": [],
                    "handCount": 5,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 47,
                },
            ],
        },
        "select": select,
        "logs": [],
    }


def test_oracle_bank_is_explicitly_research_only():
    payload = oracle_bank_payload("garchomp_spiritomb", list(range(60)))
    assert payload["status"] == "ORACLE_RESEARCH_ONLY"
    assert payload["production_evidence"] is False
    assert payload["templates"][0]["name"] == "oracle_garchomp_spiritomb"
    assert len(payload["templates"][0]["deck"]) == 60


def test_three_candidate_pairings_are_round_robin():
    assert pairings(("mewtwo_spidops", "garchomp_spiritomb", "dragapult_cinderace")) == (
        ("mewtwo_spidops", "garchomp_spiritomb"),
        ("mewtwo_spidops", "dragapult_cinderace"),
        ("garchomp_spiritomb", "dragapult_cinderace"),
    )


def test_erasure_attack_option_shape_is_detected():
    obs = _base_observation(
        {
            "type": 1,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {
                    "type": 13,
                    "inPlayArea": 4,
                    "inPlayIndex": 0,
                    "playerIndex": 0,
                    "attackId": 608,
                }
            ],
        }
    )
    truth = build_truth_state(normalize_official_observation(obs))
    assert classify_mewtwo_shape("mewtwo_spidops", truth, obs) == "ERASURE_ATTACK_OPTION"


def test_erasure_discard_window_and_effect_shape_are_detected():
    obs = _base_observation(
        {
            "type": 3,
            "context": 8,
            "minCount": 0,
            "maxCount": 2,
            "option": [
                {"type": 3, "card": 5, "playerIndex": 0},
                {"type": 3, "card": 15, "playerIndex": 0},
            ],
            "effect": {"id": 431, "serial": 9, "playerIndex": 0},
        }
    )
    truth = build_truth_state(normalize_official_observation(obs))
    assert effect_shape(obs) == {"id": 431, "serial": 9, "playerIndex": 0}
    assert classify_mewtwo_shape("mewtwo_spidops", truth, obs) == "ERASURE_DISCARD_WINDOW"


def test_non_mewtwo_candidate_is_never_tagged():
    obs = _base_observation(
        {
            "type": 1,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [{"type": 13, "attackId": 608}],
        }
    )
    truth = build_truth_state(normalize_official_observation(obs))
    assert classify_mewtwo_shape("dragapult_cinderace", truth, obs) is None

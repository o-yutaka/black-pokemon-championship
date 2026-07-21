from black_engine.official_observation import normalize_official_observation
from black_engine.truth import build_truth_state
from scripts.run_official_smoke import (
    classify_mewtwo_shape,
    effect_shape,
    option_shape,
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
                    "bench": [
                        {
                            "id": 401,
                            "serial": 10,
                            "playerIndex": 0,
                            "hp": 130,
                            "maxHp": 130,
                            "energyCards": [1, 15],
                            "tools": [],
                            "preEvolution": [400],
                        }
                    ],
                    "hand": [],
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 44,
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


def test_erasure_attack_option_shape_is_exactly_two_keys():
    raw_option = {"type": 13, "attackId": 608}
    obs = _base_observation(
        {
            "type": 1,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [raw_option],
        }
    )
    truth = build_truth_state(normalize_official_observation(obs))
    assert set(raw_option) == {"type", "attackId"}
    assert truth.options[0].attack_id == 608
    assert classify_mewtwo_shape("mewtwo_spidops", truth, obs) == "ERASURE_ATTACK_OPTION"
    assert option_shape(truth.options[0])["raw_keys"] == ["attackId", "type"]


def test_erasure_discard_window_matches_real_attached_card_contract():
    raw_option = {
        "type": 5,
        "area": 5,
        "index": 0,
        "energyIndex": 1,
        "playerIndex": 0,
    }
    obs = _base_observation(
        {
            "type": 2,
            "context": 26,
            "minCount": 0,
            "maxCount": 2,
            "option": [raw_option],
            "effect": {"id": 431, "serial": 9, "playerIndex": 0},
        }
    )
    truth = build_truth_state(normalize_official_observation(obs))
    assert effect_shape(obs) == {"id": 431, "serial": 9, "playerIndex": 0}
    assert truth.options[0].action_type == 5
    assert truth.options[0].card_id == 15
    assert truth.options[0].target_id == 401
    assert classify_mewtwo_shape("mewtwo_spidops", truth, obs) == "ERASURE_DISCARD_WINDOW"
    shape = option_shape(truth.options[0])
    assert shape["raw_keys"] == ["area", "energyIndex", "index", "playerIndex", "type"]
    assert shape["area"] == 5
    assert shape["raw_index"] == 0
    assert shape["energyIndex"] == 1
    assert shape["resolved_card_id"] == 15
    assert shape["resolved_target_id"] == 401


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

from __future__ import annotations

from black_engine.truth import build_truth_state


def player_state():
    return {
        "active": [{"id": 431, "hp": 280, "maxHp": 280, "energyCards": [{"id": 15}, {"id": 1}]}],
        "bench": [{"id": 401, "hp": 130, "maxHp": 130, "energyCards": [{"id": 1}]}],
        "hand": [{"id": 1220}, {"id": 15}],
        "handCount": 2,
        "discard": [],
        "prize": [None] * 6,
        "deckCount": 45,
    }


def observation(select):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 2,
            "result": -1,
            "players": [player_state(), {"active": [], "bench": [], "handCount": 0, "prize": [None] * 6, "deckCount": 54}],
        },
        "select": select,
        "logs": [],
    }


def test_play_option_resolves_omitted_area_from_hand():
    truth = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 7, "index": 0, "playerIndex": 0}],
    }))
    assert truth.options[0].card_id == 1220


def test_energy_option_resolves_hand_card_and_in_play_target():
    truth = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{
            "type": 8,
            "area": 2,
            "index": 1,
            "playerIndex": 0,
            "inPlayArea": 5,
            "inPlayIndex": 0,
        }],
    }))
    assert truth.options[0].card_id == 15
    assert truth.options[0].target_id == 401


def test_ability_and_attack_resolve_source_pokemon():
    ability = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 10, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0}],
    })).options[0]
    attack = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "option": [{"type": 13, "attackId": 608, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0}],
    })).options[0]
    assert ability.card_id == 401
    assert attack.card_id == 431
    assert attack.attack_id == 608


def test_public_search_deck_slice_resolves_area_deck():
    truth = build_truth_state(observation({
        "minCount": 1,
        "maxCount": 1,
        "deck": [{"id": 401}, {"id": 400}],
        "option": [{"type": 0, "area": 1, "index": 0, "playerIndex": 0}],
    }))
    assert truth.options[0].card_id == 401

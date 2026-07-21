from __future__ import annotations

import random

from black_engine.belief import ArchetypeTemplate, BayesianBeliefModel
from black_engine.truth import build_truth_state


def _setup_observation(opponent_active):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 0,
            "result": -1,
            "players": [
                {
                    "active": [],
                    "bench": [],
                    "hand": [{"id": 1, "serial": i, "playerIndex": 0} for i in range(7)],
                    "handCount": 7,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 47,
                },
                {
                    "active": opponent_active,
                    "bench": [],
                    "handCount": 6,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": 47,
                },
            ],
        },
        "select": {"type": 9, "context": 41, "minCount": 1, "maxCount": 1, "option": [{"type": 1}, {"type": 2}]},
        "logs": [],
    }


def test_face_down_active_is_reserved_and_passed_to_search_begin():
    truth = build_truth_state(_setup_observation([None]))
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", tuple([10] * 60)),))

    sample = belief.sample_hidden(truth, your_full_deck=[1] * 60, rng=random.Random(7))

    assert sample.opponent_active == (10,)
    assert len(sample.opponent_hand) == 6
    assert len(sample.opponent_prize) == 6
    assert len(sample.opponent_deck) == 47
    assert len(sample.opponent_active) + len(sample.opponent_hand) + len(sample.opponent_prize) + len(sample.opponent_deck) == 60


def test_revealed_active_is_counted_as_visible_not_resampled():
    revealed = {"id": 10, "serial": 1, "playerIndex": 1, "hp": 60, "maxHp": 60, "energyCards": [], "tools": [], "preEvolution": []}
    truth = build_truth_state(_setup_observation([revealed]))
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", tuple([10] * 60)),))

    sample = belief.sample_hidden(truth, your_full_deck=[1] * 60, rng=random.Random(7))

    assert sample.opponent_active == ()
    assert len(sample.opponent_deck) == 47
    assert len(sample.opponent_hand) + len(sample.opponent_prize) + len(sample.opponent_deck) + 1 == 60
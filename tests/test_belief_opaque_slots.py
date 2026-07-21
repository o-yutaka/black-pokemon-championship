from __future__ import annotations

import random

import black_engine.belief as belief_module
from black_engine.belief import ArchetypeTemplate, BayesianBeliefModel
from black_engine.truth import build_truth_state


def _setup_observation(opponent_active, *, stadium=None, opponent_deck_count=47, my_deck_count=47):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 0,
            "result": -1,
            "stadium": stadium if stadium is not None else [],
            "players": [
                {
                    "active": [],
                    "bench": [],
                    "hand": [{"id": 1, "serial": i, "playerIndex": 0} for i in range(7)],
                    "handCount": 7,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": my_deck_count,
                },
                {
                    "active": opponent_active,
                    "bench": [],
                    "handCount": 6,
                    "discard": [],
                    "prize": [None] * 6,
                    "deckCount": opponent_deck_count,
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

    # "not resampled" means reported from truth, not guessed -- cg.api.search_begin
    # requires a real Pokemon card id here even when it's already known/revealed,
    # so this must be the true id (10), not empty.
    assert sample.opponent_active == (10,)
    assert len(sample.opponent_deck) == 47
    assert len(sample.opponent_hand) + len(sample.opponent_prize) + len(sample.opponent_deck) + 1 == 60


def test_opponent_played_stadium_is_counted_as_visible():
    revealed = {"id": 10, "serial": 1, "playerIndex": 1, "hp": 60, "maxHp": 60, "energyCards": [], "tools": [], "preEvolution": []}
    # A played Stadium is a shared board zone, not in either player's
    # in_play/discard -- untracked, it produced a stable 1-card hidden-zone
    # accounting deficit (deck_count off by exactly 1) whenever a Stadium
    # like Team Rocket's Factory (1257) was in play.
    stadium = [{"id": 1257, "serial": 48, "playerIndex": 1}]
    truth = build_truth_state(_setup_observation([revealed], stadium=stadium, opponent_deck_count=46))
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", tuple([10] * 59) + (1257,)),))

    sample = belief.sample_hidden(truth, your_full_deck=[1] * 60, rng=random.Random(7))

    assert 1257 not in sample.opponent_deck
    assert len(sample.opponent_active) + len(sample.opponent_hand) + len(sample.opponent_prize) + len(sample.opponent_deck) == 59


def test_own_stadium_is_not_double_counted_as_opponent_visible():
    stadium = [{"id": 1257, "serial": 48, "playerIndex": 0}]  # I played it, not the opponent
    truth = build_truth_state(_setup_observation([None], stadium=stadium, my_deck_count=46))
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", tuple([10] * 60)),))
    my_deck = [1] * 59 + [1257]  # the stadium card is really in my own deck

    sample = belief.sample_hidden(truth, your_full_deck=my_deck, rng=random.Random(7))

    assert len(sample.opponent_active) + len(sample.opponent_hand) + len(sample.opponent_prize) + len(sample.opponent_deck) == 60
    assert 1257 not in sample.your_deck


def test_own_face_down_active_is_reserved_from_own_deck():
    # Symmetric with the opponent case: the engine represents *either*
    # player's just-placed, not-yet-revealed Active as active:[null] --
    # including the observing player's own side. There is no `your_active`
    # parameter to search_begin, so unlike the opponent case this only
    # needs to be reserved out of the remaining-deck pool, not reported
    # anywhere -- but it does need to be reserved, or own-side accounting
    # comes up exactly 1 card short against the real engine's deckCount.
    obs = _setup_observation([None], my_deck_count=46)
    obs["current"]["players"][0]["active"] = [None]  # my own face-down Active
    truth = build_truth_state(obs)
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", tuple([10] * 60)),))

    sample = belief.sample_hidden(truth, your_full_deck=[1] * 60, rng=random.Random(7))

    assert len(sample.your_deck) == 46
    assert len(sample.your_deck) + len(sample.your_prize) + 1 + 7 == 60  # +1 face-down active, +7 hand


def test_face_down_active_sample_is_restricted_to_pokemon_cards(monkeypatch):
    # cg.api.search_begin requires opponent_active to be a real Pokemon
    # card id -- sampling from the full remaining pool (Pokemon + Trainer +
    # Energy alike) could pick a non-Pokemon id by chance and get rejected.
    # Force the "known Pokemon ids" set so this is deterministic without a
    # real cg install.
    monkeypatch.setattr(belief_module, "_POKEMON_CARD_IDS", {10})
    truth = build_truth_state(_setup_observation([None]))
    template = tuple([10] * 3 + [999] * 57)  # 999 stands in for a non-Pokemon card
    belief = BayesianBeliefModel((ArchetypeTemplate("oracle", template),))

    for seed in range(20):
        sample = belief.sample_hidden(truth, your_full_deck=[1] * 60, rng=random.Random(seed))
        assert sample.opponent_active == (10,)
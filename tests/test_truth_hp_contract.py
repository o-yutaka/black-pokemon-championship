from __future__ import annotations

from black_engine.truth import build_truth_state


def _observation(active_hp: int, active_max_hp: int):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {
                    "active": [{"id": 380, "hp": active_hp, "maxHp": active_max_hp, "energyCards": []}],
                    "bench": [],
                    "hand": [], "handCount": 0,
                    "discard": [], "prize": [None] * 6, "deckCount": 47,
                },
                {
                    "active": [], "bench": [],
                    "hand": [], "handCount": 0,
                    "discard": [], "prize": [None] * 6, "deckCount": 53,
                },
            ],
        },
        "logs": [],
        "select": {"type": 1, "context": 0, "minCount": 1, "maxCount": 1,
                    "option": [{"type": 14}]},
    }


def test_hp_field_is_remaining_hp_not_max_hp():
    # Real cabt engine contract: `hp` is *current remaining* HP, `maxHp` is
    # the ceiling. There is no separate damage/damageCounter field -- damage
    # taken must be derived as maxHp - hp, not read from a field that never
    # exists on the wire (regression for a bug that made every Pokemon look
    # undamaged/full-HP to every guard and to ISMCTS's state heuristic).
    truth = build_truth_state(_observation(active_hp=90, active_max_hp=130))
    pokemon = truth.me.active[0]
    assert pokemon.max_hp == 130
    assert pokemon.remaining_hp == 90
    assert pokemon.damage == 40


def test_hp_field_undamaged_case_still_correct():
    truth = build_truth_state(_observation(active_hp=130, active_max_hp=130))
    pokemon = truth.me.active[0]
    assert pokemon.remaining_hp == 130
    assert pokemon.damage == 0

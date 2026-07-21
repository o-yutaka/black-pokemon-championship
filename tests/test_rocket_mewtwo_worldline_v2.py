from black_engine.rocket_mewtwo_worldline import (
    ARTICUNO,
    MEWTWO_ERASURE_BALL,
    MEWTWO_EX,
    SPIDOPS,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
    XEROSIC,
)
from black_engine.rocket_mewtwo_worldline_v2 import (
    DRAGAPULT_EX,
    RocketMewtwoWorldlinePolicy,
    erasure_attacks_required,
    planned_erasure_discards,
)


def pokemon(cid, serial, hp, max_hp, energies=()):
    return {
        "id": cid,
        "serial": serial,
        "hp": hp,
        "maxHp": max_hp,
        "energyCards": [
            {"id": energy, "serial": serial * 100 + index}
            for index, energy in enumerate(energies)
        ],
    }


def observation(
    *,
    active,
    bench,
    opponent_active=None,
    opponent_hand=5,
    options=(),
    context=-1,
    minimum=1,
    maximum=1,
    effect=None,
):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 2,
            "players": [
                {
                    "active": [active] if active else [],
                    "bench": list(bench),
                    "hand": [],
                    "discard": [],
                    "prize": [None] * 6,
                    "supporterPlayed": False,
                },
                {
                    "active": [opponent_active or pokemon(999, 900, 220, 220)],
                    "bench": [],
                    "handCount": opponent_hand,
                    "prize": [None] * 6,
                },
            ],
        },
        "select": {
            "context": context,
            "minCount": minimum,
            "maxCount": maximum,
            "effect": {"id": effect} if effect is not None else None,
            "option": list(options),
        },
    }


def rocket_board():
    return (
        pokemon(SPIDOPS, 20, 130, 130, (1,)),
        pokemon(ARTICUNO, 21, 120, 120),
        pokemon(463, 22, 80, 80),
    )


def test_320_hp_dragapult_is_zero_discard_two_hit_route():
    assert planned_erasure_discards(320, 2) == 0
    assert erasure_attacks_required(320, 0) == 2

    obs = observation(
        active=pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5)),
        bench=rocket_board(),
        opponent_active=pokemon(DRAGAPULT_EX, 900, 320, 320),
        options=(
            {"type": 14},
            {
                "type": 13,
                "attackId": MEWTWO_ERASURE_BALL,
                "playerIndex": 0,
                "inPlayArea": 4,
                "inPlayIndex": 0,
            },
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    attack = policy._plan_for_option(1, ctx)
    assert not attack.illegal
    assert attack.plan.plan_id == "ERASURE_TWO_HIT_PRESSURE"
    assert policy.choose_single(obs["select"]["option"], ctx) == 1


def test_xerosic_then_erasure_is_one_persistent_turn_plan():
    active = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    obs = observation(
        active=active,
        bench=rocket_board(),
        opponent_hand=8,
        options=(
            {"type": 7, "cardId": XEROSIC},
            {
                "type": 13,
                "attackId": MEWTWO_ERASURE_BALL,
                "playerIndex": 0,
                "inPlayArea": 4,
                "inPlayIndex": 0,
            },
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 0
    assert policy.last_runner_id == "XEROSIC_THEN_ERASURE"
    assert policy.attack_reserved

    follow = observation(
        active=active,
        bench=rocket_board(),
        opponent_hand=3,
        options=(
            {"type": 14},
            {
                "type": 13,
                "attackId": MEWTWO_ERASURE_BALL,
                "playerIndex": 0,
                "inPlayArea": 4,
                "inPlayIndex": 0,
            },
        ),
    )
    follow_ctx = policy.build_context(follow)
    assert policy.choose_single(follow["select"]["option"], follow_ctx) == 1
    assert policy.last_runner_id == "RESERVED_ERASURE_ATTACK"


def test_dragapult_matchup_holds_extra_protected_tarountula():
    obs = observation(
        active=pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5)),
        bench=(
            pokemon(SPIDOPS, 20, 130, 130, (1,)),
            pokemon(TAROUNTULA, 21, 50, 50),
            pokemon(ARTICUNO, 22, 120, 120),
            pokemon(463, 23, 80, 80),
        ),
        opponent_active=pokemon(DRAGAPULT_EX, 900, 320, 320),
        options=(
            {
                "type": 9,
                "cardId": SPIDOPS,
                "playerIndex": 0,
                "inPlayArea": 5,
                "inPlayIndex": 1,
            },
            {"type": 14},
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    evolve = policy._plan_for_option(0, ctx)
    assert evolve.illegal
    assert evolve.plan.plan_id == "HOLD_PROTECTED_BASIC"
    assert policy.choose_single(obs["select"]["option"], ctx) == 1


def test_articuno_protected_basics_preserve_power_saver_after_phantom():
    obs = observation(
        active=pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5)),
        bench=(
            pokemon(SPIDOPS, 20, 50, 130, (1,)),
            pokemon(TAROUNTULA, 21, 50, 50),
            pokemon(ARTICUNO, 22, 120, 120),
            pokemon(463, 23, 80, 80),
        ),
        opponent_active=pokemon(DRAGAPULT_EX, 900, 320, 320),
        options=({"type": 14},),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert ctx["rocket_count"] == 5
    assert ctx["rocket_count_after_phantom"] == 4
    assert ctx["four_rocket_spread_resilient"]


def test_prize_value_uses_official_card_rule_not_hp():
    from black_engine.prize_truth import prize_value

    assert prize_value(951) == 2
    assert prize_value(264) == 1
    assert prize_value(652) == 3


def test_xerosic_plan_is_stored_as_real_plan_step():
    active = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    obs = observation(
        active=active,
        bench=rocket_board(),
        opponent_hand=8,
        options=(
            {"type": 7, "cardId": XEROSIC},
            {
                "type": 13,
                "attackId": MEWTWO_ERASURE_BALL,
                "playerIndex": 0,
                "inPlayArea": 4,
                "inPlayIndex": 0,
            },
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 0
    pending = policy.pending.get()
    assert pending is not None
    assert pending.candidate.plan_id == "XEROSIC_THEN_ERASURE"
    assert len(pending.candidate.steps) == 1
    assert pending.candidate.steps[0].attack_id == MEWTWO_ERASURE_BALL

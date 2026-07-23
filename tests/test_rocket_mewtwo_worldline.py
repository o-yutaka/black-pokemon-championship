from black_engine.mewtwo_truth import PokemonInstance, build_mewtwo_truth
from black_engine.rocket_mewtwo_worldline import (
    GIOVANNI,
    MEWTWO_ERASURE_BALL,
    MEWTWO_EX,
    POKE_PAD,
    SPIDOPS,
    TEAM_ROCKET_ENERGY,
    XEROSIC,
    RocketMewtwoWorldlinePolicy,
    mewtwo_ready,
    minimum_erasure_discards,
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


def observation(*, active, bench, opponent_active=None, opponent_bench=(), opponent_hand=5, hand=(), discard=(), options=(), context=-1, minimum=1, maximum=1, effect=None):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 2,
            "players": [
                {
                    "active": [active] if active else [],
                    "bench": list(bench),
                    "hand": [{"id": cid} for cid in hand],
                    "discard": [{"id": cid} for cid in discard],
                    "prize": [None] * 6,
                    "supporterPlayed": False,
                },
                {
                    "active": [opponent_active or pokemon(999, 900, 220, 220)],
                    "bench": list(opponent_bench),
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


def test_team_rocket_energy_is_one_card_but_two_units():
    value = PokemonInstance(0, 10, MEWTWO_EX, 5, 0, 280, 280, (TEAM_ROCKET_ENERGY, 5), (1, 2))
    assert len(value.energy_card_ids) == 2
    assert value.psychic_units == 3
    assert value.total_energy_units == 3
    assert mewtwo_ready(value)


def test_erasure_minimum_physical_discard_tiers():
    assert minimum_erasure_discards(160) == 0
    assert minimum_erasure_discards(220) == 1
    assert minimum_erasure_discards(280) == 2
    assert minimum_erasure_discards(281) is None


def test_duplicate_mewtwo_options_resolve_distinct_serials():
    ready = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    building = pokemon(MEWTWO_EX, 11, 280, 280, (5,))
    obs = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(ready, building, pokemon(401, 12, 130, 130)),
        options=(
            {"type": 8, "cardId": 5, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
            {"type": 8, "cardId": 5, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 1},
        ),
    )
    truth = build_mewtwo_truth(obs)
    assert truth.options[0].target_serial == 10
    assert truth.options[1].target_serial == 11


def test_no_card_id_only_first_match_fallback():
    obs = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(pokemon(MEWTWO_EX, 10, 280, 280), pokemon(MEWTWO_EX, 11, 280, 280)),
        options=({"type": 8, "cardId": 5},),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    result = policy._plan_for_option(0, ctx)
    assert ctx["truth"].options[0].target_serial is None
    assert result.illegal


def test_ready_mewtwo_overattach_loses_to_second_mewtwo_development():
    ready = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    building = pokemon(MEWTWO_EX, 11, 280, 280, (5,))
    obs = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(ready, building, pokemon(401, 12, 130, 130), pokemon(414, 13, 120, 120)),
        options=(
            {"type": 8, "cardId": 5, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
            {"type": 8, "cardId": 5, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 1},
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 1
    assert policy.last_runner_id == "SECOND_MEWTWO_DEVELOPMENT"


def test_xerosic_is_used_only_when_it_changes_opponent_route():
    obs = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(pokemon(401, 2, 130, 130), pokemon(414, 3, 120, 120), pokemon(463, 4, 80, 80)),
        opponent_hand=7,
        options=(
            {"type": 7, "cardId": XEROSIC},
            {"type": 7, "cardId": POKE_PAD},
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 0
    assert policy.last_runner_id == "XEROSIC_PROACTIVE_CHOKE"


def test_immediate_erasure_attack_beats_xerosic():
    active = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    obs = observation(
        active=active,
        bench=(
            pokemon(SPIDOPS, 20, 130, 130, (1,)),
            pokemon(414, 21, 120, 120),
            pokemon(463, 22, 80, 80),
        ),
        opponent_hand=8,
        options=(
            {"type": 7, "cardId": XEROSIC},
            {"type": 13, "attackId": MEWTWO_ERASURE_BALL, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0},
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 1
    assert policy.last_runner_id == "ERASURE_MINIMUM_DISCARD"


def test_erasure_discards_basic_energy_from_spidops_before_special_energy():
    obs = observation(
        active=pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5)),
        bench=(
            pokemon(SPIDOPS, 20, 130, 130, (1, TEAM_ROCKET_ENERGY)),
            pokemon(414, 21, 120, 120),
            pokemon(463, 22, 80, 80),
        ),
        opponent_active=pokemon(999, 900, 220, 220),
        options=(
            {"type": 1, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0, "energyIndex": 0},
            {"type": 1, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0, "energyIndex": 1},
        ),
        context=26,
        minimum=0,
        maximum=2,
        effect=MEWTWO_EX,
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_multi(obs["select"]["option"], ctx, 0, 2) == [0]
    assert policy.last_runner_id == "ERASURE_DISCARD_1"


def test_giovanni_binds_exact_ready_mewtwo_serial():
    ready = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    obs = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(pokemon(MEWTWO_EX, 11, 280, 280, (5,)), ready, pokemon(401, 12, 130, 130), pokemon(414, 13, 120, 120)),
        opponent_bench=(pokemon(800, 901, 150, 150),),
        options=(
            {"type": 7, "cardId": GIOVANNI},
            {"type": 7, "cardId": POKE_PAD},
        ),
    )
    policy = RocketMewtwoWorldlinePolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 0
    assert policy.desired_active_serial == 10

    follow = observation(
        active=pokemon(400, 1, 50, 50),
        bench=(pokemon(MEWTWO_EX, 11, 280, 280, (5,)), ready, pokemon(401, 12, 130, 130), pokemon(414, 13, 120, 120)),
        options=(
            {"type": 1, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
            {"type": 1, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 1},
        ),
        context=3,
    )
    follow_ctx = policy.build_context(follow)
    assert policy.choose_single(follow["select"]["option"], follow_ctx) == 1
    assert policy.last_runner_id == "GIOVANNI_SELF_HANDOFF"

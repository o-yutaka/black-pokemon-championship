from black_engine.championship_policy import ChampionshipRocketMewtwoPolicy
from black_engine.rocket_mewtwo_worldline import (
    ARTICUNO,
    MEWTWO_ERASURE_BALL,
    MEWTWO_EX,
    SPIDOPS,
    SPIDOPS_ROCKET_RUSH,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
)

GRIMMSNARL_EX = 648
MIMIKYU = 434


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
    opponent_active,
    options,
    context=0,
    our_prizes=6,
    opponent_prizes=6,
    deck_count=20,
    turn=10,
):
    return {
        "current": {
            "yourIndex": 0,
            "turn": turn,
            "players": [
                {
                    "active": [active] if active else [],
                    "bench": list(bench),
                    "hand": [],
                    "discard": [],
                    "prize": [None] * our_prizes,
                    "deckCount": deck_count,
                    "supporterPlayed": False,
                },
                {
                    "active": [opponent_active] if opponent_active else [],
                    "bench": [],
                    "handCount": 5,
                    "prize": [None] * opponent_prizes,
                    "deckCount": 20,
                },
            ],
        },
        "select": {
            "context": context,
            "type": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": list(options),
        },
        "step": turn,
        "logs": [],
        "remainingOverageTime": 590,
    }


def rocket_bench_with_spidops(spidops_energies=(1, 1, 1, 1)):
    return (
        pokemon(SPIDOPS, 20, 130, 130, spidops_energies),
        pokemon(ARTICUNO, 21, 120, 120),
        pokemon(TAROUNTULA, 22, 50, 50),
        pokemon(MIMIKYU, 23, 60, 60),
    )


def test_promotion_lethal_override_selects_ready_spidops():
    obs = observation(
        active=pokemon(MEWTWO_EX, 10, 0, 280, (TEAM_ROCKET_ENERGY,)),
        bench=rocket_bench_with_spidops(),
        opponent_active=pokemon(GRIMMSNARL_EX, 900, 40, 320),
        context=3,
        our_prizes=2,
        opponent_prizes=4,
        options=(
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 1},
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 2},
        ),
    )
    policy = ChampionshipRocketMewtwoPolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 0
    assert policy.last_runner_id == "PROMOTION_LETHAL_OVERRIDE"


def test_terminal_action_freeze_attacks_instead_of_searching():
    obs = observation(
        active=pokemon(SPIDOPS, 20, 130, 130, (1, 1, 1, 1)),
        bench=(
            pokemon(MEWTWO_EX, 10, 280, 280),
            pokemon(ARTICUNO, 21, 120, 120),
            pokemon(TAROUNTULA, 22, 50, 50),
        ),
        opponent_active=pokemon(GRIMMSNARL_EX, 900, 30, 320),
        our_prizes=2,
        opponent_prizes=4,
        options=(
            {"type": 7, "cardId": 1134},
            {"type": 7, "cardId": 1219},
            {"type": 13, "attackId": SPIDOPS_ROCKET_RUSH, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0},
            {"type": 14},
        ),
    )
    policy = ChampionshipRocketMewtwoPolicy()
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 2
    assert policy.last_runner_id == "TERMINAL_ACTION_FREEZE"


def test_prize_aware_active_selection_rejects_unready_ex_into_known_lethal():
    obs = observation(
        active=pokemon(MIMIKYU, 10, 60, 60),
        bench=(
            pokemon(MEWTWO_EX, 20, 170, 280),
            pokemon(SPIDOPS, 21, 130, 130, (1, 1)),
            pokemon(ARTICUNO, 22, 120, 120),
        ),
        opponent_active=pokemon(GRIMMSNARL_EX, 900, 320, 320),
        context=3,
        our_prizes=4,
        opponent_prizes=2,
        options=(
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 0},
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 1},
            {"type": 12, "playerIndex": 0, "inPlayArea": 5, "inPlayIndex": 2},
        ),
    )
    policy = ChampionshipRocketMewtwoPolicy()
    policy.observed_damage_by_attacker[GRIMMSNARL_EX] = 360
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 1
    assert policy.last_runner_id == "PRIZE_AWARE_ACTIVE_SELECTION"


def test_observed_nonpersistent_attack_pair_is_not_repeated():
    active = pokemon(MEWTWO_EX, 10, 280, 280, (TEAM_ROCKET_ENERGY, 5))
    opponent = pokemon(999, 900, 320, 320)
    obs = observation(
        active=active,
        bench=rocket_bench_with_spidops((1,)),
        opponent_active=opponent,
        options=(
            {"type": 13, "attackId": MEWTWO_ERASURE_BALL, "playerIndex": 0, "inPlayArea": 4, "inPlayIndex": 0},
            {"type": 14},
        ),
    )
    policy = ChampionshipRocketMewtwoPolicy()
    policy.nonpersistent_attack_pairs.add((MEWTWO_EX, MEWTWO_ERASURE_BALL, 999))
    ctx = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], ctx) == 1


def test_deck_clock_suppresses_optional_search_action():
    obs = observation(
        active=pokemon(MIMIKYU, 10, 60, 60),
        bench=rocket_bench_with_spidops((1,)),
        opponent_active=pokemon(GRIMMSNARL_EX, 900, 320, 320),
        our_prizes=4,
        deck_count=5,
        options=({"type": 7, "cardId": 1134}, {"type": 14}),
    )
    policy = ChampionshipRocketMewtwoPolicy()
    ctx = policy.build_context(obs)
    assert ctx["deck_clock_critical"]
    assert policy.choose_single(obs["select"]["option"], ctx) == 1


def test_reset_episode_clears_cross_game_memory():
    policy = ChampionshipRocketMewtwoPolicy()
    policy.observed_damage_by_attacker[999] = 180
    policy.nonpersistent_attack_pairs.add((431, 608, 999))
    policy._pending_attack = (431, 608, 900, 999, 200, 4)
    policy._previous_mine_hp[10] = 100
    policy._previous_opponent_active_id = 999
    policy.desired_active_serial = 10
    policy.desired_opponent_serial = 900
    policy.last_runner_id = "DIRTY"
    policy.reset_episode()
    assert policy.observed_damage_by_attacker == {}
    assert policy.nonpersistent_attack_pairs == set()
    assert policy._pending_attack is None
    assert policy._previous_mine_hp == {}
    assert policy._previous_opponent_active_id is None
    assert policy.desired_active_serial is None
    assert policy.desired_opponent_serial is None
    assert policy.last_runner_id == "BOOT"

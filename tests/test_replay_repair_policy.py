from black_engine import ChampionshipRocketMewtwoPolicy
from black_engine.rocket_mewtwo_worldline import (
    ARTICUNO,
    MEWTWO_EX,
    MURKROW,
    SPIDOPS,
    SPIDOPS_ROCKET_RUSH,
    TAROUNTULA,
    TEAM_ROCKET_ENERGY,
)

GRIMMSNARL_EX = 648


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


def observation(*, opponent_hp=320, our_prizes=6):
    return {
        "current": {
            "yourIndex": 0,
            "turn": 5,
            "players": [
                {
                    "active": [pokemon(SPIDOPS, 10, 130, 130, (1,))],
                    "bench": [
                        pokemon(MEWTWO_EX, 20, 280, 280),
                        pokemon(TAROUNTULA, 21, 50, 50),
                        pokemon(ARTICUNO, 22, 120, 120),
                        pokemon(MURKROW, 23, 80, 80),
                    ],
                    "hand": [{"id": TEAM_ROCKET_ENERGY, "serial": 500}],
                    "discard": [],
                    "prize": [None] * our_prizes,
                    "deckCount": 30,
                    "supporterPlayed": False,
                },
                {
                    "active": [pokemon(GRIMMSNARL_EX, 900, opponent_hp, 320)],
                    "bench": [],
                    "handCount": 5,
                    "prize": [None] * 6,
                    "deckCount": 30,
                },
            ],
            "result": -1,
        },
        "select": {
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {
                    "type": 8,
                    "cardId": TEAM_ROCKET_ENERGY,
                    "playerIndex": 0,
                    "inPlayArea": 5,
                    "inPlayIndex": 0,
                },
                {
                    "type": 13,
                    "attackId": SPIDOPS_ROCKET_RUSH,
                    "playerIndex": 0,
                    "inPlayArea": 4,
                    "inPlayIndex": 0,
                },
                {"type": 14},
            ],
        },
    }


def test_replay_repair_finishes_mewtwo_setup_before_nonterminal_attack():
    obs = observation(opponent_hp=320, our_prizes=6)
    policy = ChampionshipRocketMewtwoPolicy()
    context = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], context) == 0
    assert policy.last_runner_id == "MEWTWO_SETUP_BEFORE_TURN_CLOSE"


def test_terminal_attack_remains_above_mewtwo_setup():
    obs = observation(opponent_hp=30, our_prizes=2)
    policy = ChampionshipRocketMewtwoPolicy()
    context = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], context) == 1
    assert policy.last_runner_id == "TERMINAL_ACTION_FREEZE"


def test_nonterminal_immediate_ko_is_not_delayed_for_setup():
    obs = observation(opponent_hp=120, our_prizes=6)
    policy = ChampionshipRocketMewtwoPolicy()
    context = policy.build_context(obs)
    assert policy.choose_single(obs["select"]["option"], context) == 1
    assert policy.last_runner_id != "MEWTWO_SETUP_BEFORE_TURN_CLOSE"


def test_replay_repair_can_develop_second_mewtwo_when_active_is_known_to_fall():
    obs = observation(opponent_hp=320, our_prizes=6)
    obs["current"]["players"][0]["active"] = [
        pokemon(MEWTWO_EX, 10, 170, 280, (TEAM_ROCKET_ENERGY, TEAM_ROCKET_ENERGY))
    ]
    obs["current"]["players"][0]["bench"][0] = pokemon(MEWTWO_EX, 20, 280, 280)
    obs["select"]["option"][0]["inPlayArea"] = 5
    obs["select"]["option"][0]["inPlayIndex"] = 0
    policy = ChampionshipRocketMewtwoPolicy()
    policy.observed_damage_by_attacker[GRIMMSNARL_EX] = 180
    context = policy.build_context(obs)
    assert context["ready_mewtwo"]
    assert not context["backup_attacker_ready"]
    assert policy.choose_single(obs["select"]["option"], context) == 0
    assert policy.last_runner_id == "MEWTWO_SETUP_BEFORE_TURN_CLOSE"

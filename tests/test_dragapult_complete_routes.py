from black_engine.dragapult_policy import DragapultCinderacePolicy


def _players(*, my_active=None, my_bench=None, my_hand=None, opp_active=None, opp_bench=None):
    return [
        {
            "active": my_active or [],
            "bench": my_bench or [],
            "hand": my_hand or [],
            "discard": [],
            "prize": [None] * 6,
            "deckCount": 40,
        },
        {
            "active": opp_active or [{"id": 431, "hp": 280, "maxHp": 280, "energyCards": []}],
            "bench": opp_bench or [],
            "handCount": 5,
            "discard": [],
            "prize": [None] * 6,
            "deckCount": 40,
        },
    ]


def test_recon_directive_resolves_looking_and_keeps_drakloak():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "turn": 2,
            "looking": [{"id": 120, "playerIndex": 0}, {"id": 2, "playerIndex": 0}],
            "players": _players(
                my_active=[{"id": 666, "hp": 160, "maxHp": 160, "energyCards": [{"id": 2}]}],
                my_bench=[{"id": 119, "hp": 70, "maxHp": 70, "energyCards": []}],
            ),
        },
        "select": {
            "type": 1,
            "context": 7,
            "minCount": 1,
            "maxCount": 1,
            "effect": {"id": 120},
            "option": [
                {"type": 3, "area": 12, "index": 0, "playerIndex": 0},
                {"type": 3, "area": 12, "index": 1, "playerIndex": 0},
            ],
        },
    }
    assert policy.agent(obs) == [0]


def test_phantom_dive_places_counter_for_immediate_bench_ko():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(
                my_active=[{"id": 121, "hp": 320, "maxHp": 320, "energyCards": [{"id": 2}, {"id": 5}]}],
                opp_bench=[
                    {"id": 119, "hp": 10, "maxHp": 70, "energyCards": []},
                    {"id": 121, "hp": 130, "maxHp": 320, "energyCards": []},
                ],
            ),
        },
        "select": {
            "type": 1,
            "context": 14,
            "minCount": 1,
            "maxCount": 1,
            "effect": {"id": 121},
            "option": [
                {"type": 3, "area": 5, "index": 0, "playerIndex": 1},
                {"type": 3, "area": 5, "index": 1, "playerIndex": 1},
            ],
        },
    }
    assert policy.agent(obs) == [0]


def test_rare_candy_prefers_attack_ready_dragapult_over_nonterminal_dusknoir():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(
                my_bench=[
                    {"id": 119, "hp": 70, "maxHp": 70, "energyCards": [{"id": 2}, {"id": 5}]},
                    {"id": 131, "hp": 60, "maxHp": 60, "energyCards": []},
                ],
                my_hand=[{"id": 121}, {"id": 133}],
                opp_active=[{"id": 431, "hp": 300, "maxHp": 300, "energyCards": []}],
            ),
        },
        "select": {
            "type": 7,
            "context": 37,
            "minCount": 1,
            "maxCount": 1,
            "effect": {"id": 1079},
            "option": [
                {"type": 9, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0, "playerIndex": 0},
                {"type": 9, "area": 2, "index": 1, "inPlayArea": 5, "inPlayIndex": 1, "playerIndex": 0},
            ],
        },
    }
    assert policy.agent(obs) == [0]


def test_poffin_search_is_diversity_aware_dreepy_plus_duskull():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(my_active=[{"id": 666, "hp": 160, "maxHp": 160, "energyCards": [{"id": 2}]}]),
        },
        "select": {
            "type": 1,
            "context": 5,
            "minCount": 0,
            "maxCount": 2,
            "effect": {"id": 1086},
            "deck": [{"id": 119}, {"id": 119}, {"id": 131}, {"id": 217}],
            "option": [
                {"type": 3, "area": 1, "index": 0, "playerIndex": 0},
                {"type": 3, "area": 1, "index": 1, "playerIndex": 0},
                {"type": 3, "area": 1, "index": 2, "playerIndex": 0},
                {"type": 3, "area": 1, "index": 3, "playerIndex": 0},
            ],
        },
    }
    chosen = policy.agent(obs)
    chosen_ids = {
        obs["select"]["deck"][obs["select"]["option"][index]["index"]]["id"]
        for index in chosen
    }
    assert chosen_ids == {119, 131}


def test_energy_attachment_is_instance_aware():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(
                my_bench=[
                    {"id": 121, "hp": 320, "maxHp": 320, "energyCards": [{"id": 2}]},
                    {"id": 121, "hp": 320, "maxHp": 320, "energyCards": [{"id": 2}, {"id": 5}]},
                ],
                my_hand=[{"id": 5}],
            ),
        },
        "select": {
            "type": 0,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0, "playerIndex": 0},
                {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 1, "playerIndex": 0},
            ],
        },
    }
    assert policy.agent(obs) == [0]


def test_nonterminal_cursed_blast_is_skipped():
    policy = DragapultCinderacePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(
                my_active=[{"id": 132, "hp": 90, "maxHp": 90, "energyCards": []}],
                opp_active=[{"id": 431, "hp": 280, "maxHp": 280, "energyCards": []}],
            ),
        },
        "select": {
            "type": 0,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 10, "inPlayArea": 4, "inPlayIndex": 0, "playerIndex": 0},
                {"type": 14},
            ],
        },
    }
    assert policy.agent(obs) == [1]

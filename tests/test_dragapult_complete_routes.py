from black_engine.dragapult_complete_policy import DragapultCompletePolicy


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


def test_recon_directive_resolves_real_looking_area_and_keeps_drakloak():
    policy = DragapultCompletePolicy()
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
            "type": 3,
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


def test_recon_directive_bottoms_lower_route_value_card():
    policy = DragapultCompletePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "looking": [{"id": 121, "playerIndex": 0}, {"id": 1152, "playerIndex": 0}],
            "players": _players(my_bench=[{"id": 120, "hp": 90, "maxHp": 90, "energyCards": []}]),
        },
        "select": {
            "type": 3,
            "context": 10,
            "minCount": 1,
            "maxCount": 1,
            "effect": {"id": 120},
            "option": [
                {"type": 3, "area": 12, "index": 0, "playerIndex": 0},
                {"type": 3, "area": 12, "index": 1, "playerIndex": 0},
            ],
        },
    }
    assert policy.agent(obs) == [1]


def test_rare_candy_prefers_attack_ready_dragapult_over_nonterminal_dusknoir():
    policy = DragapultCompletePolicy()
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
            "type": 9,
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


def test_poffin_multi_select_is_diversity_aware():
    policy = DragapultCompletePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(my_active=[{"id": 666, "hp": 160, "maxHp": 160, "energyCards": [{"id": 2}]}]),
        },
        "select": {
            "type": 3,
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
    selected = policy.agent(obs)
    selected_ids = {obs["select"]["deck"][obs["select"]["option"][index]["index"]]["id"] for index in selected}
    assert selected_ids == {119, 131}


def test_turbo_flare_selects_only_missing_colour_and_may_take_fewer_than_three():
    policy = DragapultCompletePolicy()
    obs = {
        "current": {
            "yourIndex": 0,
            "players": _players(
                my_active=[{"id": 666, "hp": 160, "maxHp": 160, "energyCards": [{"id": 2}]}],
                my_bench=[{"id": 119, "hp": 70, "maxHp": 70, "energyCards": [{"id": 2}]}],
            ),
        },
        "select": {
            "type": 3,
            "context": 21,
            "minCount": 0,
            "maxCount": 3,
            "effect": {"id": 666},
            "deck": [{"id": 2}, {"id": 5}, {"id": 5}],
            "option": [
                {"type": 3, "area": 1, "index": 0, "playerIndex": 0},
                {"type": 3, "area": 1, "index": 1, "playerIndex": 0},
                {"type": 3, "area": 1, "index": 2, "playerIndex": 0},
            ],
        },
    }
    selected = policy.agent(obs)
    assert len(selected) == 1
    assert obs["select"]["deck"][obs["select"]["option"][selected[0]]["index"]]["id"] == 5


def test_nonterminal_cursed_blast_is_skipped_by_base_policy():
    policy = DragapultCompletePolicy()
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

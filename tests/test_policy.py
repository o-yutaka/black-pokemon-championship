from black_engine.policy import DragapultPolicy


def _players(my_bench=None, hand=None, opp_active=None, opp_bench=None):
    return [
        {"active": [{"id": 666, "hp": 160, "maxHp": 160, "energyCards": [{"id": 2}]}], "bench": my_bench or [], "hand": hand or [], "discard": [], "deckCount": 40},
        {"active": opp_active or [{"id": 900, "hp": 280, "maxHp": 280, "energyCards": []}], "bench": opp_bench or [], "handCount": 5, "discard": [], "deckCount": 40},
    ]


def test_recon_keeps_dragapult_and_bottoms_low_value_card():
    policy = DragapultPolicy()
    base = {"yourIndex": 0, "looking": [{"id": 121}, {"id": 1152}], "players": _players(my_bench=[{"id": 120, "hp": 90, "maxHp": 90, "energyCards": []}])}
    obs_hand = {"current": base, "select": {"context": 7, "minCount": 1, "maxCount": 1, "effect": {"id": 120}, "option": [{"type": 3, "area": 12, "index": 0}, {"type": 3, "area": 12, "index": 1}]}}
    obs_bottom = {"current": base, "select": {"context": 10, "minCount": 1, "maxCount": 1, "effect": {"id": 120}, "option": [{"type": 3, "area": 12, "index": 0}, {"type": 3, "area": 12, "index": 1}]}}
    assert policy.agent(obs_hand) == [0]
    assert policy.agent(obs_bottom) == [1]


def test_poffin_diversifies_dreepy_and_duskull():
    policy = DragapultPolicy()
    obs = {"current": {"yourIndex": 0, "players": _players()}, "select": {"context": 5, "minCount": 0, "maxCount": 2, "effect": {"id": 1086}, "option": [{"type": 3, "area": 1, "index": 0}, {"type": 3, "area": 1, "index": 1}, {"type": 3, "area": 1, "index": 2}], "deck": [{"id": 119}, {"id": 119}, {"id": 131}]}}
    chosen = policy.agent(obs)
    assert {obs["select"]["deck"][obs["select"]["option"][i]["index"]]["id"] for i in chosen} == {119, 131}


def test_nonterminal_dusknoir_ability_loses_to_end_turn():
    policy = DragapultPolicy()
    obs = {"current": {"yourIndex": 0, "players": [{"active": [{"id": 133, "hp": 160, "maxHp": 160, "energyCards": []}], "bench": [], "hand": [], "discard": [], "deckCount": 40}, {"active": [{"id": 900, "hp": 280, "maxHp": 280, "energyCards": []}], "bench": [], "handCount": 5, "discard": [], "deckCount": 40}]}, "select": {"context": 0, "minCount": 1, "maxCount": 1, "option": [{"type": 10, "inPlayArea": 4, "inPlayIndex": 0, "playerIndex": 0}, {"type": 14}]}}
    assert policy.agent(obs) == [1]

from black_engine.official_observation import normalize_official_observation
from black_engine.truth import build_truth_state
from scripts.run_dragapult_complete_smoke import classify_dragapult_transition


def _obs(*, effect: int | None = None, context: int = 0, options=None):
    select = {
        "type": 0,
        "context": context,
        "minCount": 1,
        "maxCount": 1,
        "option": options or [{"type": 14}],
    }
    if effect is not None:
        select["effect"] = {"id": effect, "serial": 77, "playerIndex": 0}
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "result": -1,
            "players": [
                {"active": [{"id": 121, "serial": 1, "hp": 320, "maxHp": 320, "energyCards": []}], "bench": [], "hand": [], "discard": [], "prize": [], "deckCount": 40},
                {"active": [{"id": 431, "serial": 2, "hp": 280, "maxHp": 280, "energyCards": []}], "bench": [], "handCount": 5, "discard": [], "prize": [], "deckCount": 40},
            ],
        },
        "select": select,
        "logs": [],
    }


def _classify(obs):
    truth = build_truth_state(normalize_official_observation(obs))
    return classify_dragapult_transition(truth, obs)


def test_capture_classifies_recon_state_machine():
    assert "RECON_ACTIVATE" in _classify(_obs(effect=120, context=43, options=[{"type": 1}, {"type": 2}]))
    assert "RECON_TO_HAND" in _classify(_obs(effect=120, context=7, options=[{"type": 3, "area": 12, "index": 0, "playerIndex": 0}]))
    assert "RECON_TO_DECK_BOTTOM" in _classify(_obs(effect=120, context=10, options=[{"type": 3, "area": 12, "index": 0, "playerIndex": 0}]))


def test_capture_classifies_attacks_and_counter_windows():
    attack_tags = _classify(_obs(options=[{"type": 13, "attackId": 154}, {"type": 13, "attackId": 965}]))
    assert "PHANTOM_DIVE_ATTACK" in attack_tags
    assert "TURBO_FLARE_ATTACK" in attack_tags
    assert "PHANTOM_DIVE_COUNTER" in _classify(_obs(effect=121, context=14, options=[{"type": 3, "area": 5, "index": 0, "playerIndex": 1}]))
    assert "DUSCLOPS_COUNTER" in _classify(_obs(effect=132, context=13, options=[{"type": 3, "area": 4, "index": 0, "playerIndex": 1}]))
    assert "DUSKNOIR_COUNTER" in _classify(_obs(effect=133, context=13, options=[{"type": 3, "area": 4, "index": 0, "playerIndex": 1}]))


def test_capture_classifies_rare_candy_crispin_and_turbo_followups():
    assert "RARE_CANDY_EVOLVE" in _classify(_obs(effect=1079, context=37, options=[{"type": 9, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0, "playerIndex": 0}]))
    assert "CRISPIN_TO_HAND" in _classify(_obs(effect=1198, context=7, options=[{"type": 3, "area": 1, "index": 0, "playerIndex": 0}]))
    assert "CRISPIN_ATTACH_TARGET" in _classify(_obs(effect=1198, context=22, options=[{"type": 3, "area": 5, "index": 0, "playerIndex": 0}]))
    assert "TURBO_FLARE_ENERGY" in _classify(_obs(effect=666, context=21, options=[{"type": 3, "area": 1, "index": 0, "playerIndex": 0}]))
    assert "TURBO_FLARE_TARGET" in _classify(_obs(effect=666, context=22, options=[{"type": 3, "area": 5, "index": 0, "playerIndex": 0}]))

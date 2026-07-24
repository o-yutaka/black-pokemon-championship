from __future__ import annotations

from black_engine.support import ScoredPolicy


class DummyPolicy(ScoredPolicy):
    def build_context(self, obs: dict) -> dict:
        return {
            "me": 0,
            "current": obs["current"],
            "active_id": 121,
            "dragapult_ready": True,
            "ready_count": 1,
            "azelf_ready": False,
            "opp_hp": 220,
            "opp_damage": 0,
            "bench_slots": 3,
            "deck_count": 40,
        }

    def score_option(self, option: dict, context: dict) -> float:
        return 999.0 if option.get("type") == 8 else 100.0


def _observation() -> dict:
    return {
        "current": {
            "yourIndex": 0,
            "turn": 2,
            "players": [
                {
                    "active": [{"id": 121, "serial": 1, "hp": 320, "maxHp": 320, "energyCards": [{"id": 2}, {"id": 5}]}],
                    "bench": [{"id": 131, "serial": 2, "hp": 60, "maxHp": 60, "energyCards": []}],
                    "hand": [],
                    "discard": [],
                    "prizeCount": 6,
                    "deckCount": 40,
                },
                {
                    "active": [{"id": 900, "serial": 9, "hp": 220, "maxHp": 220, "energyCards": []}],
                    "bench": [],
                    "hand": [],
                    "discard": [],
                    "prizeCount": 6,
                    "deckCount": 40,
                },
            ],
        },
        "select": {
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 8, "cardId": 5, "inPlayArea": 5, "inPlayIndex": 0, "playerIndex": 0},
                {"type": 13, "attackId": 154},
            ],
        },
    }


def test_direct_branch_killer_changes_actual_selection_and_emits_same_evidence() -> None:
    policy = DummyPolicy()
    policy.set_deck(list(range(1, 61)))

    selection = policy.agent(_observation(), None)
    overlay = policy.get_decision_overlay()

    assert selection == [1]
    assert overlay is not None
    rejected = next(item for item in overlay["rejectedBranches"] if item["optionIndex"] == 0)
    assert rejected["reason"] == "ENERGY_WRONG_TARGET"
    assert rejected["killedBy"] == "EnergyPolicy"
    assert rejected["source"] == "ScoredPolicy.choose_single"
    assert overlay["selectedAction"]["kind"] == "ATTACK"
    assert overlay["truthLedger"]["policy"] == "DragapultPolicy"


def test_previous_search_prediction_is_compared_with_next_actual_observation() -> None:
    policy = DummyPolicy()
    policy.set_deck(list(range(1, 61)))
    policy._last_prediction = {
        "decisionId": "previous",
        "boardHash": "not-the-current-board",
        "prizeCount": 4,
        "energyCount": 0,
        "damageOnOpponent": 200,
        "attackReady": False,
    }

    policy.agent(_observation(), None)
    overlay = policy.get_decision_overlay()

    assert overlay is not None
    assert overlay["decisionDiff"]["source"] == "official_search_prediction_vs_next_observation"
    assert overlay["decisionDiff"]["matched"] is False
    assert "boardHash" in overlay["decisionDiff"]["mismatch"]

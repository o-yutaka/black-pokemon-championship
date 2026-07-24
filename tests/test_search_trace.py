from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from black_engine.search_trace import LocalSearchTracer


class FakeSearchApi:
    def __init__(self) -> None:
        self.states: dict[int, dict] = {}
        self.next_id = 1
        self.released: list[int] = []
        self.ended = False

    def search_begin(self, observation, your_deck, your_prize, opponent_deck, opponent_prize, opponent_hand, opponent_active, randomize):
        search_id = self.next_id
        self.next_id += 1
        self.states[search_id] = deepcopy(observation)
        return SimpleNamespace(searchId=search_id, observation=deepcopy(observation), result=-1)

    def search_step(self, search_id: int, selection: list[int]):
        observation = deepcopy(self.states[search_id])
        choice = selection[0]
        mine = observation["current"]["players"][0]
        opponent = observation["current"]["players"][1]
        if choice == 0:
            mine["prizeCount"] = 5
            opponent["active"][0]["hp"] = 20
        else:
            mine["active"][0]["energyCards"] = []
            mine["retreated"] = True
        observation["select"] = {"minCount": 1, "maxCount": 1, "option": [{"type": 14}]}
        child_id = self.next_id
        self.next_id += 1
        self.states[child_id] = observation
        return SimpleNamespace(searchId=child_id, observation=observation, result=-1)

    def search_release(self, search_id: int) -> None:
        self.released.append(search_id)

    def search_end(self) -> None:
        self.ended = True


def _observation() -> dict:
    return {
        "current": {
            "yourIndex": 0,
            "turn": 3,
            "players": [
                {
                    "active": [{"id": 1, "serial": 1, "hp": 100, "maxHp": 100, "energyCards": [{"id": 2}]}],
                    "bench": [],
                    "hand": [{"id": 3}],
                    "discard": [],
                    "handCount": 1,
                    "deckCount": 4,
                    "prizeCount": 2,
                },
                {
                    "active": [{"id": 11, "serial": 11, "hp": 220, "maxHp": 220, "energyCards": []}],
                    "bench": [],
                    "hand": [],
                    "discard": [],
                    "handCount": 1,
                    "deckCount": 4,
                    "prizeCount": 2,
                },
            ],
        },
        "select": {
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 13, "attackId": 154},
                {"type": 12},
            ],
        },
    }


def test_real_search_api_shape_builds_tree_counterfactual_and_cycle_evidence() -> None:
    api = FakeSearchApi()
    tracer = LocalSearchTracer(api)
    configuration = {
        "blackDecisionTrace": {
            "enabled": True,
            "playerIndex": 0,
            "opponentDeck": [11, 12, 13, 14, 15, 16, 17],
            "simulationsPerAction": 1,
            "budgetMs": 200,
        }
    }

    report = tracer.evaluate(_observation(), configuration, [1, 2, 3, 4, 5, 6, 7], [0])

    assert report["enabled"] is True
    assert report["source"] == "cg.api Search API"
    assert len(report["searchTree"]["children"]) == 2
    assert report["searchTree"]["children"][0]["visits"] == 1
    assert report["searchTree"]["children"][0]["ev"] > 0
    rejected = next(item for item in report["rejectedBranches"] if item["optionIndex"] == 1)
    assert rejected["reason"] == "RESOURCE_LOSS_CYCLE"
    assert rejected["killedBy"] == "OfficialSearchCycleGuard"
    selected = next(item for item in report["counterfactuals"] if item["selected"])
    assert selected["expectedValue"] > 0
    assert report["selectedPrediction"] is not None
    assert api.ended is True
    assert api.released


def test_search_trace_fails_closed_without_local_deck_configuration() -> None:
    report = LocalSearchTracer(FakeSearchApi()).evaluate(_observation(), None, [1, 2, 3], [0])
    assert report["enabled"] is False
    assert report["reason"] == "local trace configuration not supplied"
    assert report["searchTree"]["status"] == "unavailable"

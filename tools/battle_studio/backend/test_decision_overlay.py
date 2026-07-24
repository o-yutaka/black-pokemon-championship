from __future__ import annotations

import unittest

from decision_overlay import build_board_diff, normalize_decision_overlay, split_agent_result


class DecisionOverlayTest(unittest.TestCase):
    def test_legacy_selection_infers_action_and_official_candidates(self) -> None:
        observation = {"select": {"option": [
            {"kind": "PASS"},
            {"kind": "ABILITY", "cardId": 123, "serial": 7, "effectSource": "Drakloak"},
        ]}}
        decision = normalize_decision_overlay(observation, [1], 12.5, None)
        self.assertEqual(decision["selectedAction"]["kind"], "ABILITY")
        self.assertEqual(decision["selectedAction"]["cardId"], 123)
        self.assertTrue(decision["flags"]["abilityUsed"])
        self.assertEqual(decision["scoreSource"], "official_options_only")
        self.assertTrue(decision["candidates"][1]["selected"])

    def test_local_extended_result_preserves_scores_and_warnings(self) -> None:
        selection, overlay = split_agent_result({
            "selection": [0],
            "overlay": {
                "goal": "prize_route",
                "scores": {"policy": 42, "wastePenalty": -3},
                "warnings": ["Drakloak未使用"],
                "candidates": [{"label": "ABILITY", "score": 39, "selected": True}],
            },
        })
        decision = normalize_decision_overlay({"select": {"option": [{"kind": "ABILITY"}]}}, selection, 1.0, None, overlay)
        self.assertEqual(decision["goal"], "prize_route")
        self.assertEqual(decision["scores"]["policy"], 42.0)
        self.assertEqual(decision["warnings"], ["Drakloak未使用"])
        self.assertEqual(decision["scoreSource"], "agent")

    def test_board_diff_reports_resource_and_board_changes(self) -> None:
        before = {"turn": 1, "actingPlayer": 0, "players": [
            {"handCount": 5, "deckCount": 40, "prizeCount": 6, "discard": [], "active": {"cardId": 1, "serial": 1, "damage": 0, "energies": []}, "bench": []},
            {"handCount": 5, "deckCount": 40, "prizeCount": 6, "discard": [], "active": None, "bench": []},
        ]}
        after = {"turn": 1, "actingPlayer": 0, "players": [
            {"handCount": 4, "deckCount": 40, "prizeCount": 6, "discard": [{"cardId": 9}], "active": {"cardId": 1, "serial": 1, "damage": 20, "energies": []}, "bench": []},
            {"handCount": 5, "deckCount": 40, "prizeCount": 6, "discard": [], "active": None, "bench": []},
        ]}
        changes = build_board_diff(before, after)
        self.assertIn("P1 手札: 5→4 (-1)", changes)
        self.assertIn("P1 トラッシュ: 0→1 (+1)", changes)
        self.assertIn("P1 バトル場が変化", changes)


if __name__ == "__main__":
    unittest.main()

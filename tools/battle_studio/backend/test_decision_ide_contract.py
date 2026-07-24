from __future__ import annotations

import unittest

from decision_ide_contract import normalize_ide_fields


class DecisionIdeContractTest(unittest.TestCase):
    def test_normalizes_branch_killer_search_and_policy_layers(self) -> None:
        overlay = {
            "decisionId": 184,
            "priority": ["Energy", "Drakloak", "Candy", "Attack"],
            "expectedWinRate": 84.3,
            "searchTree": {
                "id": "root",
                "label": "Root",
                "status": "root",
                "children": [
                    {"id": "attack", "label": "Attack", "status": "available", "ev": 61, "visits": 44},
                    {"id": "ability", "label": "Ability", "status": "selected", "ev": 81, "visits": 146, "mean": 82.4, "worst": 61, "best": 89},
                ],
            },
            "rejectedBranches": [{
                "label": "Switch",
                "reason": "RESOURCE_LOOP",
                "evidence": ["Retreat Lost"],
                "metrics": {"Energy Tempo": -12, "Future Attack": "-18%"},
                "killedBy": ["CLOCK_V3", "ENERGY_POLICY"],
            }],
            "policyTrace": [{"name": "EnergyPolicy", "status": "PASS", "score": 16, "reason": "Future Damage"}],
            "truthLedger": {"Truth": "PASS", "Evidence": 5, "Engine": True},
        }
        fields = normalize_ide_fields(overlay, [])
        self.assertEqual(fields["decisionId"], "184")
        self.assertAlmostEqual(fields["expectedWinRate"], 0.843)
        self.assertEqual(fields["searchTree"]["children"][1]["visits"], 146)
        self.assertEqual(fields["rejectedBranches"][0]["killedBy"], ["CLOCK_V3", "ENERGY_POLICY"])
        self.assertEqual(fields["policyTrace"][0]["status"], "PASS")
        self.assertEqual(fields["truthLedger"]["Engine"], True)

    def test_infers_only_honest_search_data_from_candidates(self) -> None:
        candidates = [
            {"label": "Ability", "score": 81.0, "selected": True},
            {"label": "Switch", "score": 14.0, "selected": False},
            {"label": "Energy", "score": 73.0, "selected": False, "reason": "TEMPO_LOSS"},
        ]
        fields = normalize_ide_fields({}, candidates)
        tree = fields["searchTree"]
        self.assertEqual(tree["label"], "Root（公式候補から推定）")
        self.assertIsNone(tree["children"][0]["visits"])
        self.assertEqual(tree["children"][0]["status"], "selected")
        self.assertEqual(tree["children"][1]["status"], "available")
        self.assertEqual(tree["children"][2]["status"], "pruned")
        self.assertEqual(len(fields["rejectedBranches"]), 1)
        self.assertEqual(fields["rejectedBranches"][0]["reason"], "TEMPO_LOSS")


if __name__ == "__main__":
    unittest.main()

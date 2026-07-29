from __future__ import annotations

import unittest
from unittest.mock import patch

from complete_public_view import CompletePublicBattleView


def card(player: int, serial: int, card_id: int, name: str, zone: str, slot: int = 0):
    return {
        "playerIndex": player,
        "serial": serial,
        "cardId": card_id,
        "name": name,
        "zone": zone,
        "slot": slot,
        "hp": 100,
        "maxHp": 100,
        "damage": 0,
        "energies": [],
        "tools": [],
        "status": [],
        "evolution": [],
        "imageUrl": None,
    }


class CompletePublicBattleViewTest(unittest.TestCase):
    def test_subject_one_is_normalized_to_self_zero_and_keeps_eight_bench_cards(self):
        catalog = [
            {"id": value, "name": f"Card {value}", "number": str(value), "expansion": "Test", "sourceLink": ""}
            for value in range(1, 40)
        ]
        with patch("public_battle_view.get_catalog", return_value=(catalog, ())):
            view = CompletePublicBattleView("session", subject_player=1)
        frame = {
            "frameId": 3,
            "turn": 2,
            "actionCount": 4,
            "actingPlayer": 1,
            "phase": "main",
            "players": [
                {
                    "active": card(0, 1, 1, "Opponent Active", "active"),
                    "bench": [],
                    "hand": [card(0, 2, 2, "Opponent Secret", "hand")],
                    "handCount": 1,
                    "deckCount": 40,
                    "prizeCount": 6,
                    "discard": [],
                },
                {
                    "active": card(1, 3, 3, "Self Active", "active"),
                    "bench": [card(1, 10 + index, 10 + index, f"Bench {index}", "bench", index) for index in range(8)],
                    "hand": [card(1, 30, 30, "Self Hand", "hand")],
                    "handCount": 1,
                    "deckCount": 35,
                    "prizeCount": 4,
                    "discard": [card(1, 31, 31, "Self Discard", "discard")],
                },
            ],
            "stadium": card(1, 32, 32, "Area Zero", "unknown"),
            "events": [{"type": "turn", "actor": 1, "text": "turn"}],
            "decision": {"actor": 1, "goal": "attack", "chosen": "attack", "candidates": []},
            "result": None,
        }
        public, cards = view.render(frame)
        self.assertEqual(public["players"][0]["name"], "自分")
        self.assertEqual(public["players"][1]["name"], "相手")
        self.assertEqual(len(public["players"][0]["bench"]), 8)
        self.assertEqual(len(public["players"][0]["hand"]), 1)
        self.assertEqual(public["players"][1]["hand"], [])
        self.assertEqual(public["actingPlayer"], 0)
        self.assertEqual(public["decision"]["actor"], 0)
        self.assertEqual(public["events"][0]["actor"], 0)
        self.assertEqual(public["players"][0]["active"]["playerIndex"], 0)
        self.assertEqual(public["players"][1]["active"]["playerIndex"], 1)
        self.assertGreaterEqual(len(cards), 12)
        self.assertNotIn("Opponent Secret", str(public))


if __name__ == "__main__":
    unittest.main()

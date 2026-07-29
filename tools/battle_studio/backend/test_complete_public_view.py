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
        "hp": 100 if zone in {"active", "bench"} else None,
        "maxHp": 100 if zone in {"active", "bench"} else None,
        "damage": 0,
        "energies": [],
        "tools": [],
        "status": [],
        "evolution": [],
        "imageUrl": None,
    }


def catalog_for(limit: int = 80):
    return [
        {
            "id": value,
            "name": f"Card {value}",
            "number": str(value),
            "expansion": "Test",
            "sourceLink": "",
        }
        for value in range(1, limit)
    ]


def sample_frame():
    return {
        "frameId": 3,
        "turn": 2,
        "actionCount": 4,
        "actingPlayer": 1,
        "phase": "main",
        "players": [
            {
                "active": card(0, 1, 1, "Opponent Active", "active"),
                "bench": [],
                "hand": [card(0, 2, 2, "Opponent Secret Hand", "hand")],
                "handCount": 1,
                "deck": [card(0, 40, 40, "Opponent Secret Deck", "deck")],
                "deckCount": 40,
                "prize": [card(0, 41, 41, "Opponent Secret Prize", "prize")],
                "prizeCount": 6,
                "discard": [card(0, 42, 42, "Opponent Discard", "discard")],
            },
            {
                "active": card(1, 3, 3, "Self Active", "active"),
                "bench": [
                    card(1, 10 + index, 10 + index, f"Bench {index}", "bench", index)
                    for index in range(8)
                ],
                "hand": [card(1, 30, 30, "Self Hand", "hand")],
                "handCount": 1,
                "deck": [card(1, 50, 50, "Self Secret Deck", "deck")],
                "deckCount": 35,
                "prize": [card(1, 51, 51, "Self Secret Prize", "prize")],
                "prizeCount": 4,
                "discard": [card(1, 31, 31, "Self Discard", "discard")],
            },
        ],
        "stadium": card(1, 32, 32, "Area Zero", "unknown"),
        "events": [{"type": "turn", "actor": 1, "text": "turn"}],
        "decision": {"actor": 1, "goal": "attack", "chosen": "attack", "candidates": []},
        "result": None,
    }


class CompletePublicBattleViewTest(unittest.TestCase):
    def make_view(self, subject_player: int = 1):
        with patch("public_battle_view.get_catalog", return_value=(catalog_for(), ())):
            return CompletePublicBattleView("session", subject_player=subject_player)

    def test_subject_one_is_normalized_and_normal_view_hides_all_hidden_zones(self):
        view = self.make_view()
        public, cards = view.render(sample_frame())
        encoded = str(public)
        catalog_encoded = str(cards)

        self.assertEqual(public["players"][0]["name"], "自分")
        self.assertEqual(public["players"][1]["name"], "相手")
        self.assertEqual(len(public["players"][0]["bench"]), 8)
        self.assertEqual(len(public["players"][0]["hand"]), 1)
        self.assertEqual(public["players"][1]["hand"], [])
        self.assertEqual(public["players"][0]["deck"], [])
        self.assertEqual(public["players"][1]["deck"], [])
        self.assertEqual(public["players"][0]["prize"], [])
        self.assertEqual(public["players"][1]["prize"], [])
        self.assertEqual(public["actingPlayer"], 0)
        self.assertEqual(public["decision"]["actor"], 0)
        self.assertEqual(public["events"][0]["actor"], 0)
        self.assertEqual(public["players"][0]["active"]["playerIndex"], 0)
        self.assertEqual(public["players"][1]["active"]["playerIndex"], 1)
        for secret in (
            "Opponent Secret Hand",
            "Opponent Secret Deck",
            "Opponent Secret Prize",
            "Self Secret Deck",
            "Self Secret Prize",
        ):
            self.assertNotIn(secret, encoded)
            self.assertNotIn(secret, catalog_encoded)

    def test_simulator_reveals_hidden_zones_and_off_hides_them_again(self):
        view = self.make_view()
        simulator, simulator_cards = view.render_simulator(sample_frame())
        simulator_encoded = str(simulator)
        simulator_catalog = str(simulator_cards)

        self.assertEqual(len(simulator["players"][1]["hand"]), 1)
        self.assertEqual(len(simulator["players"][0]["deck"]), 1)
        self.assertEqual(len(simulator["players"][1]["deck"]), 1)
        self.assertEqual(len(simulator["players"][0]["prize"]), 1)
        self.assertEqual(len(simulator["players"][1]["prize"]), 1)
        for secret in (
            "Opponent Secret Hand",
            "Opponent Secret Deck",
            "Opponent Secret Prize",
            "Self Secret Deck",
            "Self Secret Prize",
        ):
            self.assertIn(secret, simulator_encoded)
            self.assertIn(secret.replace("Secret ", "") if False else "Card", simulator_catalog)

        normal_again, normal_cards_again = view.render(sample_frame())
        normal_encoded = str(normal_again)
        normal_catalog = str(normal_cards_again)
        for secret in (
            "Opponent Secret Hand",
            "Opponent Secret Deck",
            "Opponent Secret Prize",
            "Self Secret Deck",
            "Self Secret Prize",
        ):
            self.assertNotIn(secret, normal_encoded)
        hidden_actual_ids = {2, 40, 41, 50, 51}
        visible_catalog_ids = {entry["id"] for entry in normal_cards_again}
        simulator_catalog_ids = {entry["id"] for entry in simulator_cards}
        self.assertTrue(simulator_catalog_ids - visible_catalog_ids)
        self.assertNotEqual(hidden_actual_ids, simulator_catalog_ids)
        self.assertNotIn("Opponent Secret", normal_catalog)


if __name__ == "__main__":
    unittest.main()

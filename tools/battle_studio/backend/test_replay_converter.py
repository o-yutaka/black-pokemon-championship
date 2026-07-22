from __future__ import annotations

import unittest

from replay_converter import ConversionError, convert


class ReplayConverterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "snapshots": [
                {
                    "turn": 2,
                    "actingPlayer": 0,
                    "current": {
                        "players": [
                            {
                                "name": "A",
                                "active": {"serial": 10, "cardId": 121, "name": "Dragapult ex", "hp": 300, "maxHp": 320},
                                "bench": [{"serial": 11, "cardId": 120, "name": "Drakloak", "hp": 90, "maxHp": 90}],
                                "handCount": 5,
                                "deckCount": 33,
                                "prizeCount": 5,
                            },
                            {
                                "name": "B",
                                "active": {"serial": 20, "cardId": 900, "hp": 100, "maxHp": 220},
                                "bench": [],
                                "handCount": 4,
                                "deckCount": 34,
                                "prizeCount": 6,
                            },
                        ]
                    },
                    "logs": [{"type": "attack", "playerIndex": 0, "text": "attack"}],
                }
            ]
        }

    def test_converts_complete_snapshot(self) -> None:
        result = convert(self.payload, "r1", "cabt", "player_view")
        self.assertEqual(result["schemaVersion"], "1.0")
        self.assertEqual(result["frames"][0]["players"][0]["active"]["serial"], 10)
        self.assertEqual(result["frames"][0]["players"][0]["active"]["damage"], 20)
        self.assertEqual(result["frames"][0]["events"][0]["type"], "attack")

    def test_rejects_card_without_serial(self) -> None:
        self.payload["snapshots"][0]["current"]["players"][0]["active"].pop("serial")
        with self.assertRaises(ConversionError):
            convert(self.payload, "r1", "cabt", "unknown")

    def test_rejects_missing_player_pair(self) -> None:
        self.payload["snapshots"][0]["current"]["players"] = []
        with self.assertRaises(ConversionError):
            convert(self.payload, "r1", "cabt", "unknown")

    def test_skips_opaque_hidden_hand_cards_without_inference(self) -> None:
        player = self.payload["snapshots"][0]["current"]["players"][1]
        player["hand"] = [
            {"hidden": True},
            {"serial": 21, "cardId": 901, "name": "Visible card"},
        ]
        result = convert(self.payload, "r1", "cabt", "player_view")
        normalized = result["frames"][0]["players"][1]
        self.assertEqual(normalized["handCount"], 4)
        self.assertEqual([card["serial"] for card in normalized["hand"]], [21])

    def test_does_not_infer_stadium_owner_from_turn_player(self) -> None:
        self.payload["snapshots"][0]["current"]["stadium"] = {"serial": 30, "cardId": 777, "name": "Stadium"}
        result = convert(self.payload, "r1", "cabt", "player_view")
        self.assertIsNone(result["frames"][0]["stadium"])

    def test_preserves_stadium_when_owner_is_observed(self) -> None:
        self.payload["snapshots"][0]["current"]["stadium"] = {
            "serial": 30,
            "cardId": 777,
            "name": "Stadium",
            "playerIndex": 1,
        }
        result = convert(self.payload, "r1", "cabt", "player_view")
        self.assertEqual(result["frames"][0]["stadium"]["playerIndex"], 1)

    def test_normalizes_supported_decision_trace_only(self) -> None:
        self.payload["snapshots"][0]["decision"] = {
            "actor": 0,
            "goal": "prize route",
            "chosen": "attack",
            "confidence": 0.8,
            "elapsedMs": 12,
            "candidates": [{"label": "attack", "score": 4.2, "selected": True}],
        }
        result = convert(self.payload, "r1", "cabt", "player_view")
        decision = result["frames"][0]["decision"]
        self.assertEqual(decision["chosen"], "attack")
        self.assertEqual(decision["candidates"][0]["score"], 4.2)


if __name__ == "__main__":
    unittest.main()

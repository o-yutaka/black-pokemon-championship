from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from public_battle_view import PublicBattleView


CARD_ID = 987654321
SERIAL = 123456789


def card(player: int, zone: str, slot: int | None = None) -> dict[str, object]:
    return {
        "playerIndex": player,
        "serial": SERIAL + player,
        "cardId": CARD_ID + player,
        "name": "Dragapult ex" if player == 0 else "Rocket Mewtwo ex",
        "zone": zone,
        "slot": slot,
        "hp": 200,
        "maxHp": 320,
        "damage": 120,
        "energies": ["Psychic"],
        "tools": [],
        "status": [],
        "evolution": [CARD_ID - 1],
        "imageUrl": None,
    }


def frame() -> dict[str, object]:
    return {
        "frameId": 4,
        "turn": 3,
        "actionCount": 8,
        "actingPlayer": 0,
        "phase": "main",
        "players": [
            {
                "name": "Player bundle path /tmp/internal",
                "active": card(0, "active", 0),
                "bench": [],
                "hand": [card(0, "hand", 0)],
                "handCount": 1,
                "deckCount": 42,
                "prizeCount": 5,
                "discard": [],
                "supporterPlayed": False,
                "retreated": False,
            },
            {
                "name": "Opponent",
                "active": card(1, "active", 0),
                "bench": [],
                "hand": [card(1, "hand", 0)],
                "handCount": 4,
                "deckCount": 39,
                "prizeCount": 4,
                "discard": [],
                "supporterPlayed": True,
                "retreated": False,
            },
        ],
        "stadium": None,
        "events": [
            {"type": "agent_error", "actor": 0, "text": "Traceback File \"agent.py\" serial=123"},
            {"type": "attack", "actor": 0, "text": "ワザを使った"},
        ],
        "decision": {
            "actor": 0,
            "goal": "次の攻撃を準備",
            "chosen": "[0]",
            "confidence": 0.8,
            "elapsedMs": 12.5,
            "candidates": [
                {"label": "ATTACK", "score": 74, "selected": True, "cardId": CARD_ID, "serial": SERIAL},
            ],
            "selectedAction": {"optionIndex": 0, "arrayIndex": 2, "serial": SERIAL},
            "hiddenBelief": {"secret": 0.9},
            "truthLedger": {"area": 4},
            "searchTree": {
                "id": "raw-root-id",
                "label": "Attack",
                "status": "root",
                "ev": 0.74,
                "visits": 5,
                "mean": 0.7,
                "worst": 0.2,
                "best": 0.9,
                "reason": None,
                "children": [],
            },
        },
        "result": None,
    }


class PublicBattleViewTests(unittest.TestCase):
    def build(self, nonce: str = "session-a") -> PublicBattleView:
        catalog = [{
            "id": CARD_ID,
            "name": "Dragapult ex",
            "number": "130",
            "expansion": "Test Set",
            "sourceLink": "https://example.test/card/dragapult",
        }]
        with patch("public_battle_view.get_catalog", return_value=(catalog, ())):
            return PublicBattleView(nonce, subject_player=0)

    def test_hides_opponent_hand_and_internal_identifiers(self) -> None:
        view = self.build()
        public_frame, public_cards = view.render(frame())
        encoded = json.dumps({"frame": public_frame, "cards": public_cards}, ensure_ascii=False)

        self.assertEqual(len(public_frame["players"][0]["hand"]), 1)
        self.assertEqual(public_frame["players"][1]["hand"], [])
        self.assertEqual(public_frame["players"][1]["handCount"], 4)
        self.assertNotIn(str(CARD_ID), encoded)
        self.assertNotIn(str(SERIAL), encoded)
        self.assertNotIn("selectedAction", public_frame["decision"])
        self.assertNotIn("hiddenBelief", public_frame["decision"])
        self.assertNotIn("truthLedger", public_frame["decision"])
        self.assertNotEqual(public_frame["decision"]["searchTree"]["id"], "raw-root-id")
        self.assertEqual(public_frame["decision"]["chosen"], "ATTACK")
        self.assertEqual(public_frame["events"][0]["text"], "対戦AIがこの行動を完了できませんでした")
        self.assertIn("Dragapult ex", {entry["name"] for entry in public_cards})

    def test_opaque_ids_are_stable_only_inside_one_session(self) -> None:
        first, _ = self.build("session-a").render(frame())
        repeated_view = self.build("session-a")
        repeated, _ = repeated_view.render(frame())
        other, _ = self.build("session-b").render(frame())

        first_card = first["players"][0]["active"]
        repeated_card = repeated["players"][0]["active"]
        other_card = other["players"][0]["active"]
        self.assertEqual(first_card["cardId"], repeated_card["cardId"])
        self.assertEqual(first_card["serial"], repeated_card["serial"])
        self.assertNotEqual(first_card["cardId"], other_card["cardId"])
        self.assertNotEqual(first_card["serial"], other_card["serial"])


if __name__ == "__main__":
    unittest.main()

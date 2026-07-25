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
        "energies": [44444444, "Psychic"],
        "tools": [{"cardId": 55555555}],
        "status": [],
        "evolution": [CARD_ID - 1],
        "imageUrl": None,
    }


def frame(zone: str = "active", slot: int = 0) -> dict[str, object]:
    own = card(0, zone, slot)
    opponent_hand = card(1, "hand", 0)
    return {
        "frameId": 4,
        "turn": 3,
        "actionCount": 8,
        "actingPlayer": 0,
        "phase": "main",
        "players": [
            {
                "name": "Player /tmp/internal/main.py",
                "active": own,
                "bench": [],
                "hand": [own],
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
                "hand": [opponent_hand],
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
            {
                "type": "agent_error",
                "actor": 0,
                "text": 'Traceback File "agent.py" serial=123',
            },
            {
                "type": "attack",
                "actor": 0,
                "text": "path=/home/user/HROS/private observation data",
            },
        ],
        "decision": {
            "actor": 0,
            "goal": "searchId=123456789 /tmp/private",
            "chosen": "[0]",
            "confidence": 0.8,
            "elapsedMs": 12.5,
            "candidates": [
                {
                    "label": "ATTACK",
                    "score": 74,
                    "selected": True,
                    "cardId": CARD_ID,
                    "serial": SERIAL,
                }
            ],
            "selectedAction": {
                "optionIndex": 0,
                "arrayIndex": 2,
                "serial": SERIAL,
            },
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
                "reason": "/tmp/tree",
                "children": [],
            },
            "rejectedBranches": [
                {
                    "label": "Switch",
                    "reason": "context=MAIN",
                    "evidence": ["serial 123456789"],
                    "metrics": {
                        "ev": 0.3,
                        "raw": "/tmp/leak",
                        "id": "123456789",
                    },
                    "killedBy": ["optionIndex=3"],
                }
            ],
        },
        "result": None,
    }


class PublicBattleViewTests(unittest.TestCase):
    def build(self, nonce: str = "session-a") -> PublicBattleView:
        catalog = [
            {
                "id": CARD_ID,
                "name": "Dragapult ex",
                "number": "130",
                "expansion": "Test Set",
                "sourceLink": "https://images.pokemontcg.io/test/130.png",
            },
            {
                "id": 44444444,
                "name": "Basic Psychic Energy",
                "number": "001",
                "expansion": "Energy",
                "sourceLink": "file:///tmp/secret",
            },
            {
                "id": 55555555,
                "name": "Safe Tool",
                "number": "002",
                "expansion": "Tool",
                "sourceLink": "https://evil.example/private",
            },
        ]
        with patch("public_battle_view.get_catalog", return_value=(catalog, ())):
            return PublicBattleView(nonce, subject_player=0)

    def test_hides_opponent_hand_and_all_internal_identifiers(self) -> None:
        public_frame, public_cards = self.build().render(frame())
        encoded = json.dumps(
            {"frame": public_frame, "cards": public_cards},
            ensure_ascii=False,
        )
        self.assertEqual(public_frame["players"][1]["hand"], [])
        self.assertEqual(public_frame["players"][1]["handCount"], 4)
        for secret in (
            str(CARD_ID),
            str(SERIAL),
            "44444444",
            "55555555",
            "/tmp",
            "/home/user",
            "selectedAction",
            "hiddenBelief",
            "truthLedger",
            "optionIndex",
            "searchId",
        ):
            self.assertNotIn(secret, encoded)
        self.assertEqual(public_frame["players"][0]["name"], "自分")
        self.assertEqual(public_frame["players"][1]["name"], "相手")
        self.assertEqual(public_frame["decision"]["chosen"], "ATTACK")
        self.assertEqual(
            public_frame["decision"]["rejectedBranches"][0]["metrics"],
            {"ev": 0.3},
        )
        self.assertIn(
            "Basic Psychic Energy",
            public_frame["players"][0]["active"]["energies"],
        )
        self.assertIn(
            "Safe Tool",
            public_frame["players"][0]["active"]["tools"],
        )
        self.assertTrue(
            any(
                entry["sourceLink"].startswith("https://images.pokemontcg.io/")
                for entry in public_cards
            )
        )
        self.assertFalse(
            any(
                "evil.example" in entry["sourceLink"]
                or "file:" in entry["sourceLink"]
                for entry in public_cards
            )
        )

    def test_instance_identity_survives_zone_and_slot_changes(self) -> None:
        view = self.build()
        active, _ = view.render(frame("active", 0))
        moved, _ = view.render(frame("bench", 4))
        self.assertEqual(
            active["players"][0]["active"]["serial"],
            moved["players"][0]["active"]["serial"],
        )

    def test_opaque_ids_change_between_sessions(self) -> None:
        first, _ = self.build("session-a").render(frame())
        other, _ = self.build("session-b").render(frame())
        self.assertNotEqual(
            first["players"][0]["active"]["cardId"],
            other["players"][0]["active"]["cardId"],
        )
        self.assertNotEqual(
            first["players"][0]["active"]["serial"],
            other["players"][0]["active"]["serial"],
        )


if __name__ == "__main__":
    unittest.main()

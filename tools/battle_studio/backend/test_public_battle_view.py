from __future__ import annotations

import unittest

from public_battle_view import public_battle_frame, public_error


class PublicBattleViewTest(unittest.TestCase):
    def sample_frame(self):
        card = {
            "playerIndex": 0,
            "serial": 918273,
            "cardId": 42,
            "name": "Visible Card",
            "zone": "active",
            "slot": 0,
            "hp": 100,
            "maxHp": 120,
            "damage": 20,
            "energies": ["Psychic"],
            "tools": [],
            "status": [],
            "evolution": [10, 42],
            "imageUrl": None,
            "area": 7,
            "index": 3,
        }
        hidden = {**card, "playerIndex": 1, "serial": 222, "cardId": 99, "name": "Secret Hand", "zone": "hand"}
        player = {
            "name": "Player bundle /tmp/private/main.py",
            "active": card,
            "bench": [],
            "hand": [card],
            "handCount": 1,
            "deckCount": 50,
            "prizeCount": 6,
            "discard": [],
            "supporterPlayed": False,
            "retreated": False,
        }
        opponent = {**player, "name": "Opponent", "active": {**card, "playerIndex": 1, "serial": 123}, "hand": [hidden]}
        return {
            "frameId": 1,
            "turn": 2,
            "actionCount": 3,
            "actingPlayer": 0,
            "phase": "main",
            "players": [player, opponent],
            "stadium": None,
            "events": [{"type": "engine", "actor": 0, "text": "selection index=3 /tmp/private/libcg.so", "cardKey": "0:918273"}],
            "decision": {
                "actor": 0,
                "goal": "Attack",
                "chosen": "Attach",
                "confidence": 0.7,
                "elapsedMs": 12,
                "searchTree": {"id": "root"},
                "truthLedger": {"serial": 918273},
                "hiddenBelief": {"x": 0.5},
                "selectedAction": {"optionIndex": 3},
            },
            "result": None,
            "observation": {"select": {"option": [1, 2]}},
        }

    def test_whitelists_frame_and_hides_opponent_hand(self):
        public = public_battle_frame(self.sample_frame(), b"a" * 32, subject_player=0)
        self.assertEqual(set(public), {"frameId", "turn", "actionCount", "actingPlayer", "phase", "players", "stadium", "events", "decision", "result"})
        self.assertEqual(public["players"][0]["hand"][0]["cardId"], 42)
        self.assertEqual(public["players"][1]["hand"], [])
        self.assertEqual(public["players"][1]["handCount"], 1)
        self.assertNotEqual(public["players"][0]["active"]["serial"], 918273)
        self.assertNotIn("area", public["players"][0]["active"])
        self.assertNotIn("index", public["players"][0]["active"])

    def test_decision_is_summary_only(self):
        decision = public_battle_frame(self.sample_frame(), b"b" * 32)["decision"]
        self.assertEqual(set(decision), {"actor", "goal", "chosen", "confidence", "elapsedMs", "warnings", "candidates"})
        self.assertNotIn("searchTree", decision)
        self.assertNotIn("truthLedger", decision)
        self.assertNotIn("hiddenBelief", decision)
        self.assertNotIn("selectedAction", decision)

    def test_paths_and_internal_words_are_redacted(self):
        public = public_battle_frame(self.sample_frame(), b"c" * 32)
        self.assertNotIn("/tmp/private", public["players"][0]["name"])
        self.assertEqual(public["events"][0]["text"], "内部処理は非公開です")
        self.assertIsNone(public["events"][0]["cardKey"])

    def test_public_error_never_contains_engine_detail(self):
        payload = public_error(RuntimeError("official Select rejected selection=[3] code=9 /tmp/libcg.so"))
        self.assertEqual(payload["code"], "ACTION_UNAVAILABLE")
        self.assertNotIn("Select", payload["detail"])
        self.assertNotIn("libcg", payload["detail"])

    def test_opaque_serial_is_stable_per_session_and_changes_between_sessions(self):
        first = public_battle_frame(self.sample_frame(), b"x" * 32)["players"][0]["active"]["serial"]
        repeat = public_battle_frame(self.sample_frame(), b"x" * 32)["players"][0]["active"]["serial"]
        other = public_battle_frame(self.sample_frame(), b"y" * 32)["players"][0]["active"]["serial"]
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, other)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _card(player: int, serial: int, card_id: int, name: str, zone: str, slot: int | None, hp: int | None, max_hp: int | None, damage: int = 0, energies: list[str] | None = None) -> dict[str, Any]:
    return {
        "playerIndex": player,
        "serial": serial,
        "cardId": card_id,
        "name": name,
        "zone": zone,
        "slot": slot,
        "hp": hp,
        "maxHp": max_hp,
        "damage": damage,
        "energies": energies or [],
        "tools": [],
        "status": [],
        "evolution": [],
        "imageUrl": None,
    }


@dataclass
class EmulatorState:
    frame_id: int = 0
    turn: int = 1
    acting_player: int = 0
    p0_damage: int = 0
    p1_damage: int = 0
    result: str | None = None


class CabtShapeEmulator:
    """Deterministic CABT-shaped engine for transport and UI integration tests."""

    name = "cabt-shape-emulator"

    def __init__(self) -> None:
        self.state = EmulatorState()

    async def start(self) -> dict[str, Any]:
        self.state = EmulatorState()
        return self._frame("battle_start", "Emulator battle started")

    async def step(self, selection: list[int]) -> dict[str, Any]:
        if self.state.result is not None:
            raise ValueError("battle already finished")
        if selection != [0]:
            raise ValueError("emulator accepts only legal selection [0]")

        self.state.frame_id += 1
        if self.state.acting_player == 0:
            self.state.p1_damage += 60
            text = "Dragapult ex used Phantom Dive"
        else:
            self.state.p0_damage += 40
            text = "Rocket's Mewtwo ex used Erasure Ball"

        if self.state.p1_damage >= 180:
            self.state.result = "P0_WIN"
        elif self.state.p0_damage >= 180:
            self.state.result = "P1_WIN"
        else:
            self.state.acting_player = 1 - self.state.acting_player
            if self.state.acting_player == 0:
                self.state.turn += 1

        return self._frame("attack", text)

    async def close(self) -> None:
        return None

    def legal_selections(self) -> list[list[int]]:
        return [] if self.state.result is not None else [[0]]

    def _frame(self, event_type: str, event_text: str) -> dict[str, Any]:
        p0_hp = max(0, 320 - self.state.p0_damage)
        p1_hp = max(0, 280 - self.state.p1_damage)
        return {
            "frameId": self.state.frame_id,
            "turn": self.state.turn,
            "actionCount": self.state.frame_id,
            "actingPlayer": self.state.acting_player,
            "phase": "result" if self.state.result else "main",
            "players": [
                {
                    "name": "BLACK Dragapult",
                    "active": _card(0, 1001, 121, "Dragapult ex", "active", 0, p0_hp, 320, self.state.p0_damage, ["Psychic", "Fire"]),
                    "bench": [_card(0, 1002, 133, "Dusknoir", "bench", 0, 160, 160)],
                    "hand": [],
                    "handCount": 5,
                    "deckCount": 42 - self.state.frame_id,
                    "prizeCount": 6 if self.state.result != "P0_WIN" else 5,
                    "discard": [],
                    "supporterPlayed": False,
                    "retreated": False,
                },
                {
                    "name": "Rocket Mewtwo",
                    "active": _card(1, 2001, 702, "Team Rocket's Mewtwo ex", "active", 0, p1_hp, 280, self.state.p1_damage, ["Psychic"]),
                    "bench": [_card(1, 2002, 703, "Team Rocket's Spidops", "bench", 0, 130, 130, 0, ["Rocket"])],
                    "hand": [],
                    "handCount": 4,
                    "deckCount": 43 - self.state.frame_id,
                    "prizeCount": 6 if self.state.result != "P1_WIN" else 5,
                    "discard": [],
                    "supporterPlayed": False,
                    "retreated": False,
                },
            ],
            "stadium": None,
            "events": [{"type": event_type, "actor": self.state.acting_player, "text": event_text, "cardKey": None}],
            "decision": {
                "actor": self.state.acting_player,
                "goal": "terminal" if self.state.result else "prize_route",
                "chosen": "selection[0]",
                "confidence": 1.0,
                "elapsedMs": 1.0,
                "candidates": [{"label": "selection[0]", "score": 1.0, "selected": True}],
            },
            "result": self.state.result,
        }

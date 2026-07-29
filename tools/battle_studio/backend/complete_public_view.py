from __future__ import annotations

from typing import Any, Mapping, Sequence

from public_battle_view import PublicBattleView


def _items(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


class CompletePublicBattleView(PublicBattleView):
    """Player-safe view with every public card zone and viewer-normalized seating."""

    def _player(self, raw: Any, player: int) -> dict[str, Any]:
        projected = super()._player(raw, player)
        value = raw if isinstance(raw, Mapping) else {}
        projected["bench"] = [
            card
            for item in _items(value.get("bench"))
            if (card := self._card(item, player)) is not None
        ][:8]
        return projected

    @staticmethod
    def _swap_player_index(card: Any) -> None:
        if isinstance(card, dict) and card.get("playerIndex") in (0, 1):
            card["playerIndex"] = 1 - int(card["playerIndex"])

    def _normalize_to_viewer(self, frame: dict[str, Any]) -> None:
        if self.subject_player == 0:
            return
        players = frame.get("players")
        if not isinstance(players, list) or len(players) != 2:
            return
        players[0], players[1] = players[1], players[0]
        for player in players:
            if not isinstance(player, dict):
                continue
            self._swap_player_index(player.get("active"))
            for zone in ("bench", "hand", "discard"):
                for card in _items(player.get(zone)):
                    self._swap_player_index(card)
        self._swap_player_index(frame.get("stadium"))
        if frame.get("actingPlayer") in (0, 1):
            frame["actingPlayer"] = 1 - int(frame["actingPlayer"])
        decision = frame.get("decision")
        if isinstance(decision, dict) and decision.get("actor") in (0, 1):
            decision["actor"] = 1 - int(decision["actor"])
        for event in _items(frame.get("events")):
            if isinstance(event, dict) and event.get("actor") in (0, 1):
                event["actor"] = 1 - int(event["actor"])

    def render(self, frame: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        public_frame, cards = super().render(frame)
        self._normalize_to_viewer(public_frame)
        return public_frame, cards

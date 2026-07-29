from __future__ import annotations

from typing import Any, Mapping, Sequence

from public_battle_view import PublicBattleView


def _items(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


class CompletePublicBattleView(PublicBattleView):
    """Player-safe view plus an explicit local simulator projection."""

    def _zone_cards(self, value: Any, player: int, zone: str, limit: int) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for item in _items(value):
            card = self._card(item, player)
            if card is None:
                continue
            card["zone"] = zone
            if card.get("slot") is None:
                card["slot"] = len(cards)
            cards.append(card)
            if len(cards) >= limit:
                break
        return cards

    def _player(self, raw: Any, player: int) -> dict[str, Any]:
        projected = super()._player(raw, player)
        value = raw if isinstance(raw, Mapping) else {}
        projected["bench"] = self._zone_cards(value.get("bench"), player, "bench", 8)
        projected["deck"] = []
        projected["prize"] = []
        return projected

    def _simulator_player(self, raw: Any, player: int) -> dict[str, Any]:
        value = raw if isinstance(raw, Mapping) else {}
        projected = super()._player(raw, player)
        projected["bench"] = self._zone_cards(value.get("bench"), player, "bench", 8)
        projected["hand"] = self._zone_cards(value.get("hand"), player, "hand", 60)
        projected["deck"] = self._zone_cards(value.get("deck", value.get("deckCards")), player, "deck", 60)
        projected["prize"] = self._zone_cards(value.get("prize", value.get("prizes", value.get("prizeCards"))), player, "prize", 6)
        projected["discard"] = self._zone_cards(value.get("discard", value.get("discardPile")), player, "discard", 60)
        projected["handCount"] = max(int(projected.get("handCount", 0)), len(projected["hand"]))
        projected["deckCount"] = max(int(projected.get("deckCount", 0)), len(projected["deck"]))
        projected["prizeCount"] = max(int(projected.get("prizeCount", 0)), len(projected["prize"]))
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
            for zone in ("bench", "hand", "deck", "prize", "discard"):
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

    def _visible_catalog(self, frame: Mapping[str, Any]) -> list[dict[str, Any]]:
        visible: set[int] = set()

        def add(card: Any) -> None:
            if not isinstance(card, Mapping):
                return
            card_id = card.get("cardId")
            if isinstance(card_id, int) and card_id > 0:
                visible.add(card_id)
            for evolution_id in _items(card.get("evolution")):
                if isinstance(evolution_id, int) and evolution_id > 0:
                    visible.add(evolution_id)

        add(frame.get("stadium"))
        for player in _items(frame.get("players")):
            if not isinstance(player, Mapping):
                continue
            add(player.get("active"))
            for zone in ("bench", "hand", "deck", "prize", "discard"):
                for card in _items(player.get(zone)):
                    add(card)
        return [dict(self._catalog_entries[card_id]) for card_id in sorted(visible) if card_id in self._catalog_entries]

    def render(self, frame: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        public_frame, _cards = super().render(frame)
        for player in public_frame.get("players", []):
            if isinstance(player, dict):
                player.setdefault("deck", [])
                player.setdefault("prize", [])
        self._normalize_to_viewer(public_frame)
        return public_frame, self._visible_catalog(public_frame)

    def render_simulator(self, frame: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        public_frame, _cards = super().render(frame)
        raw_players = _items(frame.get("players"))
        if len(raw_players) != 2:
            raise ValueError("simulator view requires exactly two players")
        public_frame["players"] = [self._simulator_player(raw_players[0], 0), self._simulator_player(raw_players[1], 1)]
        self._normalize_to_viewer(public_frame)
        return public_frame, self._visible_catalog(public_frame)

from __future__ import annotations

from typing import Any

# Generated from the competition card table EN_Card_Data(4).csv.
# Prize value is a card rule, never an HP heuristic.
POKEMON_EX_IDS = frozenset((
    24, 29, 30, 37, 40, 44, 46, 52, 63, 75, 79, 80, 83, 84, 96, 99, 107, 108, 117, 121, 125, 130, 138,
    139, 140, 141, 150, 153, 154, 161, 176, 179, 184, 189, 190, 193, 198, 205, 207, 210, 223, 229, 231,
    232, 236, 239, 241, 243, 244, 246, 248, 249, 259, 269, 272, 283, 293, 299, 302, 306, 313, 316, 320,
    326, 328, 329, 331, 336, 337, 340, 357, 369, 372, 381, 389, 404, 407, 424, 431, 447, 455, 458, 471,
    481, 509, 515, 525, 527, 547, 561, 573, 583, 598, 618, 631, 641, 648, 795, 806, 813, 835, 911, 944,
    951, 954, 957, 962, 968, 969, 975, 979, 984, 988, 990, 993, 997, 1002, 1022, 1026, 1062, 1071
))

MEGA_POKEMON_EX_IDS = frozenset((
    652, 662, 678, 687, 695, 723, 737, 747, 754, 756, 766, 772, 781, 790, 828, 849, 861, 868, 886, 896,
    904, 919, 928, 932, 939, 1006, 1031, 1040, 1056, 1064
))


def prize_value(card_or_id: Any) -> int:
    """Return Prizes taken for knocking out one Pokémon.

    Unknown or ordinary Pokémon default to one Prize. The official card-rule
    sets are authoritative; HP must never infer Prize value.
    """
    if isinstance(card_or_id, dict):
        raw = card_or_id.get("rule") or card_or_id.get("Rule")
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized == "mega pokémon ex":
                return 3
            if normalized == "pokémon ex":
                return 2
        card_id = -1
        for key in ("id", "card", "cardId", "pokemonId"):
            value = card_or_id.get(key)
            if type(value) is int:
                card_id = value
                break
    else:
        card_id = card_or_id if type(card_or_id) is int else -1

    if card_id in MEGA_POKEMON_EX_IDS:
        return 3
    if card_id in POKEMON_EX_IDS:
        return 2
    return 1

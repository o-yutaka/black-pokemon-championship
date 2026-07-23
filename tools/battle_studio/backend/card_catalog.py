from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

CARD_FILE = "EN_Card_Data.csv"
ID_FILE = "card_id_list.csv"


def _candidate_roots() -> list[Path]:
    resolved = Path(__file__).resolve()
    repo = resolved.parents[3] if len(resolved.parents) > 3 else resolved.parent
    roots = [
        Path.cwd(), repo, repo / "data", repo / "assets", repo / "submission",
        Path("/home/user/HROS"), Path("/home/user/HROS/data"), Path("/home/user/HROS/submission"),
    ]
    configured = os.environ.get("BLACK_CARD_DATA_DIR")
    if configured:
        roots.insert(0, Path(configured).expanduser())
    result: list[Path] = []
    for root in roots:
        root = root.resolve()
        if root not in result:
            result.append(root)
    return result


def discover_card_files() -> tuple[Path, Path]:
    for root in _candidate_roots():
        card = root / CARD_FILE
        ids = root / ID_FILE
        if card.is_file() and ids.is_file():
            return card, ids
    raise FileNotFoundError(
        f"{CARD_FILE} and {ID_FILE} were not found together; set BLACK_CARD_DATA_DIR"
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number_text(value: str) -> str:
    value = _text(value)
    if value.endswith(".0"):
        return value[:-2]
    return value


def load_catalog(card_path: Path, id_path: Path) -> list[dict[str, Any]]:
    cards: dict[int, dict[str, Any]] = {}
    with id_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            card_id = int(row["card_id"])
            cards[card_id] = {
                "id": card_id,
                "name": _text(row.get("card_name")),
                "expansion": _text(row.get("expansion")),
                "number": _number_text(row.get("collection_no", "")),
                "kind": "", "stage": "", "previous": "", "hp": "", "type": "", "rule": "",
                "moves": [], "basicEnergy": False, "basicPokemon": False, "ace": False,
            }

    rows_by_id: dict[int, list[dict[str, str]]] = defaultdict(list)
    with card_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows_by_id[int(row["Card ID"])].append(row)

    for card_id, rows in rows_by_id.items():
        first = rows[0]
        card = cards.setdefault(card_id, {"id": card_id, "moves": []})
        stage = _text(first.get("Stage (Pokémon)/Type (Energy and Trainer)"))
        category = _text(first.get("Category"))
        card.update({
            "name": _text(first.get("Card Name")) or card.get("name", f"Card {card_id}"),
            "expansion": _text(first.get("Expansion")) or card.get("expansion", ""),
            "number": _number_text(first.get("Collection No.", "")) or card.get("number", ""),
            "kind": category or stage,
            "stage": stage,
            "previous": _text(first.get("Previous stage")),
            "hp": _number_text(first.get("HP", "")),
            "type": _text(first.get("Type")),
            "rule": _text(first.get("Rule")),
        })
        seen: set[tuple[str, str, str, str]] = set()
        moves: list[dict[str, str]] = []
        for row in rows:
            move = (
                _text(row.get("Move Name")), _text(row.get("Cost")),
                _number_text(row.get("Damage", "")), _text(row.get("Effect Explanation")),
            )
            if not any(move) or move in seen:
                continue
            seen.add(move)
            moves.append({"name": move[0], "cost": move[1], "damage": move[2], "text": move[3]})
        card["moves"] = moves
        identity = f"{stage} {category} {card.get('rule', '')} {card.get('name', '')}".lower()
        card["basicEnergy"] = "basic energy" in identity
        card["basicPokemon"] = "basic" in stage.lower() and "energy" not in stage.lower() and bool(card.get("hp"))
        card["ace"] = "ace spec" in identity

    return [cards[key] for key in sorted(cards)]


_cache_key: tuple[str, int, str, int] | None = None
_cache_value: list[dict[str, Any]] | None = None


def get_catalog() -> tuple[list[dict[str, Any]], tuple[Path, Path]]:
    global _cache_key, _cache_value
    card_path, id_path = discover_card_files()
    key = (str(card_path), card_path.stat().st_mtime_ns, str(id_path), id_path.stat().st_mtime_ns)
    if _cache_key != key or _cache_value is None:
        _cache_value = load_catalog(card_path, id_path)
        _cache_key = key
    return _cache_value, (card_path, id_path)

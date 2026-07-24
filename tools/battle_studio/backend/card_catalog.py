from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

CARD_FILE = "EN_Card_Data.csv"
ID_FILE = "card_id_list.csv"
_SKIP_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", ".venv-battle-studio"}
_MAX_DISCOVERY_DEPTH = 6


def _candidate_roots() -> list[Path]:
    resolved = Path(__file__).resolve()
    repo = resolved.parents[3] if len(resolved.parents) > 3 else resolved.parent
    roots = [
        Path.cwd(),
        repo,
        repo / "data",
        repo / "assets",
        repo / "submission",
        Path("/home/user/HROS"),
        Path("/home/user/HROS/data"),
        Path("/home/user/HROS/submission"),
        Path.home(),
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


def _file_suffix(name: str, canonical: str) -> int | None:
    stem = re.escape(Path(canonical).stem)
    match = re.fullmatch(rf"{stem}(?:\s*\((\d+)\))?\.csv", name, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1) or 0)


def _matching_files(directory: Path, canonical: str) -> list[Path]:
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    matches = [entry for entry in entries if entry.is_file() and _file_suffix(entry.name, canonical) is not None]
    return sorted(matches, key=lambda path: (_file_suffix(path.name, canonical) == 0, path.stat().st_mtime_ns), reverse=True)


def _best_pair(directory: Path) -> tuple[Path, Path] | None:
    cards = _matching_files(directory, CARD_FILE)
    ids = _matching_files(directory, ID_FILE)
    if not cards or not ids:
        return None

    def score(pair: tuple[Path, Path]) -> tuple[int, int, int]:
        card, id_file = pair
        card_suffix = _file_suffix(card.name, CARD_FILE) or 0
        id_suffix = _file_suffix(id_file.name, ID_FILE) or 0
        same_suffix = int(card_suffix == id_suffix)
        exact_count = int(card_suffix == 0) + int(id_suffix == 0)
        newest_common = min(card.stat().st_mtime_ns, id_file.stat().st_mtime_ns)
        return same_suffix, exact_count, newest_common

    return max(((card, id_file) for card in cards for id_file in ids), key=score)


def _walk_directories(root: Path, max_depth: int = _MAX_DISCOVERY_DEPTH) -> Iterable[Path]:
    if not root.is_dir():
        return
    base_depth = len(root.parts)
    for directory, subdirectories, _files in os.walk(root):
        current = Path(directory)
        depth = len(current.parts) - base_depth
        subdirectories[:] = [
            name for name in subdirectories
            if name not in _SKIP_DIRECTORIES and not (name.startswith(".") and name != ".")
        ]
        if depth >= max_depth:
            subdirectories.clear()
        yield current


def discover_card_files(roots: list[Path] | None = None) -> tuple[Path, Path]:
    searched: list[str] = []
    for root in roots or _candidate_roots():
        root = root.expanduser().resolve()
        searched.append(str(root))
        direct = _best_pair(root)
        if direct:
            return direct
        for directory in _walk_directories(root):
            if directory == root:
                continue
            pair = _best_pair(directory)
            if pair:
                return pair
    accepted = f"{CARD_FILE} / EN_Card_Data(<番号>).csv と {ID_FILE} / card_id_list(<番号>).csv"
    raise FileNotFoundError(
        f"カードDBが見つかりません。対応ファイル名: {accepted}。検索先: {', '.join(searched)}。"
        "別の場所にある場合は BLACK_CARD_DATA_DIR を指定してください"
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

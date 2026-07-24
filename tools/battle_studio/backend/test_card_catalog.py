from pathlib import Path

from card_catalog import discover_card_files, load_catalog


def _write_minimal_pair(directory: Path, suffix: str = "") -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    ids = directory / f"card_id_list{suffix}.csv"
    ids.write_text("card_id,card_name,expansion,collection_no,link\n1,Basic {G} Energy,SVE,1,x\n10,Testmon,TST,10,x\n20,Prime Thing,TST,20,x\n", encoding="utf-8")
    cards = directory / f"EN_Card_Data{suffix}.csv"
    header = "Card ID,Card Name,Expansion,Collection No.,Stage (Pokémon)/Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation\n"
    rows = [
        "1,Basic {G} Energy,SVE,1,Basic Energy,,,,,{G},,,,,,,,,",
        "10,Testmon,TST,10,Basic Pokémon,,Pokémon,,70,{G},,,,,Leafage,{G},10,",
        "10,Testmon,TST,10,Basic Pokémon,,Pokémon,,70,{G},,,,,Grow,{G},,Draw a card.",
        "20,Prime Thing,TST,20,Item,ACE SPEC,Trainer,,,,,,,,,,,,",
    ]
    cards.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return cards, ids


def test_catalog_merges_attack_rows_and_flags(tmp_path: Path) -> None:
    cards, ids = _write_minimal_pair(tmp_path)
    catalog = load_catalog(cards, ids)
    by_id = {card["id"]: card for card in catalog}
    assert by_id[1]["basicEnergy"] is True
    assert by_id[10]["basicPokemon"] is True
    assert len(by_id[10]["moves"]) == 2
    assert by_id[20]["ace"] is True


def test_discovery_accepts_download_suffix_and_nested_directory(tmp_path: Path) -> None:
    expected_cards, expected_ids = _write_minimal_pair(tmp_path / "uploads" / "engine-data", "(5)")
    cards, ids = discover_card_files([tmp_path])
    assert cards == expected_cards
    assert ids == expected_ids


def test_discovery_prefers_exact_names_over_numbered_copies(tmp_path: Path) -> None:
    exact_cards, exact_ids = _write_minimal_pair(tmp_path)
    _write_minimal_pair(tmp_path, "(9)")
    cards, ids = discover_card_files([tmp_path])
    assert cards == exact_cards
    assert ids == exact_ids

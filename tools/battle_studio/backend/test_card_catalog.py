from pathlib import Path

from card_catalog import load_catalog


def test_catalog_merges_attack_rows_and_flags(tmp_path: Path) -> None:
    ids = tmp_path / "card_id_list.csv"
    ids.write_text("card_id,card_name,expansion,collection_no,link\n1,Basic {G} Energy,SVE,1,x\n10,Testmon,TST,10,x\n20,Prime Thing,TST,20,x\n", encoding="utf-8")
    cards = tmp_path / "EN_Card_Data.csv"
    header = "Card ID,Card Name,Expansion,Collection No.,Stage (Pokémon)/Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation\n"
    rows = [
        "1,Basic {G} Energy,SVE,1,Basic Energy,,,,,{G},,,,,,,,",
        "10,Testmon,TST,10,Basic Pokémon,,Pokémon,,70,{G},,,,,Leafage,{G},10,",
        "10,Testmon,TST,10,Basic Pokémon,,Pokémon,,70,{G},,,,,Grow,{G},,Draw a card.",
        "20,Prime Thing,TST,20,Item,ACE SPEC,Trainer,,,,,,,,,,,",
    ]
    cards.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    catalog = load_catalog(cards, ids)
    by_id = {card["id"]: card for card in catalog}
    assert by_id[1]["basicEnergy"] is True
    assert by_id[10]["basicPokemon"] is True
    assert len(by_id[10]["moves"]) == 2
    assert by_id[20]["ace"] is True

from pathlib import Path

from card_catalog import load_catalog


def test_catalog_preserves_source_link(tmp_path: Path) -> None:
    ids = tmp_path / "card_id_list.csv"
    ids.write_text("card_id,card_name,expansion,collection_no,link\n10,Testmon,TST,10,https://images.pokemontcg.io/tst/10.png\n", encoding="utf-8")
    cards = tmp_path / "EN_Card_Data.csv"
    cards.write_text("Card ID,Card Name,Expansion,Collection No.,Stage (Pokémon)/Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation\n10,Testmon,TST,10,Basic Pokémon,,Pokémon,,70,{G},,,,,Leafage,{G},10,\n", encoding="utf-8")
    catalog = load_catalog(cards, ids)
    assert catalog[0]["sourceLink"] == "https://images.pokemontcg.io/tst/10.png"

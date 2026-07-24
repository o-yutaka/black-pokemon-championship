from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from card_catalog import install_catalog_folder
from native_artifacts import NativeArtifactError, NativeArtifactStore


class FolderUploadTests(unittest.TestCase):
    def test_registers_extracted_agent_folder_without_tar(self) -> None:
        with TemporaryDirectory() as directory:
            store = NativeArtifactStore(Path(directory) / "runtime")
            deck = "\n".join(str(value) for value in range(1, 61)).encode()
            artifact = store.register_bundle_files("agent", [
                ("selected-agent/main.py", b"def agent(observation, configuration): return [0]\n"),
                ("selected-agent/deck.csv", deck),
                ("selected-agent/black_engine/policy.py", b"# policy\n"),
            ])
            self.assertEqual(artifact.filename, "agent")
            self.assertEqual(len(artifact.deck), 60)
            self.assertEqual(artifact.root.name, "selected-agent")

    def test_rejects_ambiguous_parent_folder(self) -> None:
        with TemporaryDirectory() as directory:
            store = NativeArtifactStore(Path(directory) / "runtime")
            deck = "\n".join(str(value) for value in range(1, 61)).encode()
            with self.assertRaisesRegex(NativeArtifactError, "検出 2件"):
                store.register_bundle_files("parent", [
                    ("one/main.py", b"x"), ("one/deck.csv", deck),
                    ("two/main.py", b"x"), ("two/deck.csv", deck),
                ])

    def test_activates_card_database_from_selected_folder(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "cards"
            ids = b"card_id,card_name,expansion,collection_no,link\n1,Testmon,TST,1,\n"
            cards = (
                "Card ID,Card Name,Expansion,Collection No.,Stage (Pok\xc3\xa9mon)/Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation\n"
                "1,Testmon,TST,1,Basic Pok\xc3\xa9mon,,Pok\xc3\xa9mon,,70,{P},,,,,Test,{P},10,\n"
            ).encode()
            catalog, sources = install_catalog_folder(root, [
                ("download/EN_Card_Data(5).csv", cards),
                ("download/card_id_list(5).csv", ids),
            ])
            self.assertEqual(catalog[0]["name"], "Testmon")
            self.assertEqual(sources[0].name, "EN_Card_Data(5).csv")


if __name__ == "__main__":
    unittest.main()

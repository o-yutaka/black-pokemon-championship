from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from artifact_store import ArtifactError, ArtifactStore


def bundle_bytes(deck: list[int], extra: dict[str, bytes] | None = None) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        files = {"main.py": b"def agent(obs, configuration=None): return [0]\n", "deck.csv": ("\n".join(map(str, deck)) + "\n").encode()}
        files.update(extra or {})
        for name, data in files.items():
            info = tarfile.TarInfo(name); info.size = len(data); archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def test_bundle_requires_exact_60(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactError, match="exactly 60"):
        store.register_bundle("bad.tgz", bundle_bytes([1] * 59))


def test_bundle_rejects_traversal(tmp_path: Path) -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        info = tarfile.TarInfo("../evil"); info.size = 1; archive.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ArtifactError, match="unsafe archive path"):
        ArtifactStore(tmp_path).register_bundle("bad.tgz", output.getvalue())


def test_bundle_accepts_root_kaggle_shape(tmp_path: Path) -> None:
    artifact = ArtifactStore(tmp_path).register_bundle("ok.tgz", bundle_bytes([1] * 60))
    assert len(artifact.deck) == 60
    assert {"main.py", "deck.csv"}.issubset(artifact.members)


def test_card_catalog_groups_moves(tmp_path: Path) -> None:
    card_ids = b"card_id,card_name,expansion,collection_no,link\n21,Hawlucha,TST,1,https://example.invalid/21\n"
    card_data = ("Card ID,Card Name,Expansion,Collection No.,Stage (Pok\xc3\xa9mon)/Type (Energy and Trainer),Rule,Category,Previous stage,HP,Type,Weakness,Resistance (Type),Retreat,Move Name,Cost,Damage,Effect Explanation\n"
                 "21,Hawlucha,TST,1,Basic,n/a,Pok\xc3\xa9mon,n/a,80,{F},,,1,Nab n Dash,{C},0,Draw\n"
                 "21,Hawlucha,TST,1,Basic,n/a,Pok\xc3\xa9mon,n/a,80,{F},,,1,High Jump Kick,{F}{C},100,\n").encode()
    attacks = json.dumps([{"attackId": 1, "name": "Nab n Dash", "text": "Draw", "damage": 0, "energies": [0]}]).encode()
    catalog = ArtifactStore(tmp_path).register_card_catalog([("card_id_list.csv", card_ids), ("EN_Card_Data.csv", card_data), ("attack_id_mapping.json", attacks)])
    assert len(catalog.records[21].moves) == 2
    assert catalog.records[21].hp == 80

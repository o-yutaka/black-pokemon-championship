from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from bundle_manager import BundleError, BundleStore


def make_bundle(first: str = "main.py", deck_count: int = 60) -> io.BytesIO:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tf:
        files = {
            first: b"def agent(obs, config=None): return []\n",
            "deck.csv": ("\n".join(str(i % 10 + 1) for i in range(deck_count)) + "\n").encode(),
            "cg/libcg.so": b"\x7fELFfake",
        }
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    out.seek(0)
    return out


def test_valid_bundle(tmp_path: Path) -> None:
    info = BundleStore(tmp_path).ingest(make_bundle(), "submission.tgz")
    assert len(info.deck) == 60
    assert info.engine_sha256


def test_main_must_be_first(tmp_path: Path) -> None:
    with pytest.raises(BundleError, match="main.py must be the first"):
        BundleStore(tmp_path).ingest(make_bundle(first="readme.txt"), "submission.tgz")


def test_deck_must_have_sixty_ids(tmp_path: Path) -> None:
    with pytest.raises(BundleError, match="exactly 60"):
        BundleStore(tmp_path).ingest(make_bundle(deck_count=59), "submission.tgz")

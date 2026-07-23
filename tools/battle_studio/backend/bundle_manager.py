from __future__ import annotations

import csv
import hashlib
import io
import shutil
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

MAX_BUNDLE_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 400
REQUIRED = {"main.py", "deck.csv", "cg/libcg.so"}
ALLOWED_PREFIXES = ("black_engine/", "cg/")
ALLOWED_ROOT = {"main.py", "deck.csv", "submission_contract.py"}


class BundleError(ValueError):
    pass


@dataclass(frozen=True)
class BundleInfo:
    bundle_id: str
    root: Path
    archive_sha256: str
    engine_sha256: str
    deck: tuple[int, ...]
    members: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"bundleId": self.bundle_id, "archiveSha256": self.archive_sha256, "engineSha256": self.engine_sha256, "deckCount": len(self.deck), "deck": list(self.deck), "members": list(self.members)}


class BundleStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, BundleInfo] = {}

    def get(self, bundle_id: str) -> BundleInfo:
        try:
            return self._items[bundle_id]
        except KeyError as exc:
            raise BundleError("unknown bundle") from exc

    def ingest(self, stream: BinaryIO, filename: str) -> BundleInfo:
        if not filename.lower().endswith((".tar.gz", ".tgz")):
            raise BundleError("Kaggle bundle must be .tar.gz or .tgz")
        bundle_id = uuid.uuid4().hex
        work = self.root / bundle_id
        work.mkdir(parents=True)
        archive = work / "bundle.tgz"
        digest = hashlib.sha256()
        total = 0
        with archive.open("wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BUNDLE_BYTES:
                    raise BundleError("bundle exceeds 100 MB")
                digest.update(chunk)
                out.write(chunk)
        extract_root = work / "root"
        extract_root.mkdir()
        try:
            members = self._safe_extract(archive, extract_root)
            deck = self._read_deck(extract_root / "deck.csv")
            engine_path = extract_root / "cg" / "libcg.so"
            if engine_path.read_bytes()[:4] != b"\x7fELF":
                raise BundleError("cg/libcg.so is not an ELF binary")
            engine_sha = hashlib.sha256(engine_path.read_bytes()).hexdigest()
            info = BundleInfo(bundle_id, extract_root, digest.hexdigest(), engine_sha, tuple(deck), tuple(members))
            self._items[bundle_id] = info
            return info
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise

    def _safe_extract(self, archive: Path, destination: Path) -> list[str]:
        try:
            tf = tarfile.open(archive, "r:gz")
        except tarfile.TarError as exc:
            raise BundleError(f"invalid gzip tar: {exc}") from exc
        with tf:
            members = tf.getmembers()
            if not members or len(members) > MAX_MEMBERS:
                raise BundleError("invalid member count")
            names: list[str] = []
            seen: set[str] = set()
            for i, member in enumerate(members):
                name = member.name.replace("\\", "/")
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or not path.parts:
                    raise BundleError(f"unsafe path: {name}")
                if name in seen:
                    raise BundleError(f"duplicate path: {name}")
                seen.add(name)
                if member.issym() or member.islnk() or member.isdev():
                    raise BundleError(f"links/devices forbidden: {name}")
                if member.size > MAX_MEMBER_BYTES:
                    raise BundleError(f"member too large: {name}")
                if i == 0 and name != "main.py":
                    raise BundleError("main.py must be the first archive entry")
                if member.isfile():
                    if name not in ALLOWED_ROOT and not name.startswith(ALLOWED_PREFIXES):
                        raise BundleError(f"unexpected file: {name}")
                    names.append(name)
            missing = REQUIRED.difference(names)
            if missing:
                raise BundleError("missing: " + ", ".join(sorted(missing)))
            tf.extractall(destination, filter="data")
            return names

    @staticmethod
    def _read_deck(path: Path) -> list[int]:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BundleError("deck.csv must be UTF-8") from exc
        rows = list(csv.reader(io.StringIO(text)))
        values: list[int] = []
        for row in rows:
            for cell in row:
                cell = cell.strip()
                if not cell:
                    continue
                try:
                    values.append(int(cell))
                except ValueError:
                    if not values:
                        continue
                    raise BundleError(f"invalid deck card id: {cell}")
        if len(values) != 60:
            raise BundleError(f"deck.csv must contain exactly 60 ids, found {len(values)}")
        return values

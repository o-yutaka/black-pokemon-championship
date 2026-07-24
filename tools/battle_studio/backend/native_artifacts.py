from __future__ import annotations

import csv
import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_ENGINE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 10_000


class NativeArtifactError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(name: str) -> Path:
    pure = PurePosixPath(name.replace("\\", "/"))
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise NativeArtifactError(f"unsafe archive path: {name}")
    return Path(*pure.parts)


def _read_deck(path: Path) -> tuple[int, ...]:
    values: list[int] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            for cell in row:
                raw = cell.strip()
                if not raw:
                    continue
                if not raw.isdigit():
                    if not values and raw.lower().replace(" ", "_") in {"card_id", "cardid", "id"}:
                        continue
                    raise NativeArtifactError(f"deck.csv contains non-integer card id: {raw}")
                values.append(int(raw))
    if len(values) != 60 or any(value <= 0 for value in values):
        raise NativeArtifactError(f"deck.csv must contain exactly 60 positive card IDs, found {len(values)}")
    return tuple(values)


@dataclass(frozen=True)
class EngineArtifact:
    artifact_id: str
    filename: str
    library_path: Path
    sha256: str
    source_kind: str
    compiler: str | None

    def public(self) -> dict[str, object]:
        return {"id": self.artifact_id, "filename": self.filename, "sha256": self.sha256, "sourceKind": self.source_kind, "compiler": self.compiler}


@dataclass(frozen=True)
class BundleArtifact:
    artifact_id: str
    filename: str
    root: Path
    sha256: str
    deck: tuple[int, ...]
    bundled_engine_sha256: str | None

    def public(self) -> dict[str, object]:
        return {"id": self.artifact_id, "filename": self.filename, "sha256": self.sha256, "deckCount": len(self.deck), "uniqueCardIds": len(set(self.deck)), "bundledEngineSha256": self.bundled_engine_sha256}


class NativeArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(tempfile.mkdtemp(prefix="black-native-runtime-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.engines: dict[str, EngineArtifact] = {}
        self.bundles: dict[str, BundleArtifact] = {}

    def register_engine(self, filename: str, data: bytes) -> EngineArtifact:
        if not data or len(data) > MAX_ENGINE_BYTES:
            raise NativeArtifactError("engine upload is empty or too large")
        artifact_id = uuid.uuid4().hex
        target = self.root / "engines" / artifact_id
        target.mkdir(parents=True)
        compiler: str | None = None
        if data.startswith(b"\x7fELF"):
            library = target / "libcg.so"
            library.write_bytes(data)
            source_kind = "linux-shared-library"
        elif zipfile.is_zipfile(io.BytesIO(data)):
            source = target / "source"
            source.mkdir()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_MEMBERS:
                    raise NativeArtifactError("engine ZIP has too many members")
                extracted: list[Path] = []
                for info in infos:
                    if info.is_dir():
                        continue
                    relative = _safe_path(info.filename)
                    out = source / relative
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as incoming, out.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    extracted.append(out)
            exports = [path for path in extracted if path.name == "Export.cpp"]
            if len(exports) != 1 or not any(path.name == "README.md" for path in extracted) or not any(path.name.startswith("LicenseRef-") for path in extracted):
                raise NativeArtifactError("engine ZIP is not the recognizable official source package")
            library = target / "libcg.so"
            compiler = os.environ.get("CXX", "g++")
            completed = subprocess.run([compiler, "-std=c++20", "-O2", "-fPIC", "-shared", "Export.cpp", "-o", str(library)], cwd=exports[0].parent, capture_output=True, text=True, timeout=180, check=False)
            if completed.returncode != 0 or not library.is_file():
                raise NativeArtifactError(f"engine compile failed: {(completed.stderr or completed.stdout)[-4000:]}")
            source_kind = "official-source-zip-compiled-locally"
            shutil.rmtree(source, ignore_errors=True)
        else:
            raise NativeArtifactError("engine must be Linux libcg.so or official source ZIP")
        artifact = EngineArtifact(artifact_id, filename, library, _sha256_file(library), source_kind, compiler)
        self.engines[artifact_id] = artifact
        return artifact

    def register_bundle(self, filename: str, data: bytes, expected_engine_sha256: str | None = None) -> BundleArtifact:
        if not data or len(data) > MAX_BUNDLE_BYTES:
            raise NativeArtifactError("bundle upload is empty or too large")
        artifact_id = uuid.uuid4().hex
        root = self.root / "bundles" / artifact_id
        root.mkdir(parents=True)
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                members = archive.getmembers()
                if len(members) > MAX_MEMBERS:
                    raise NativeArtifactError("bundle has too many members")
                for member in members:
                    relative = _safe_path(member.name)
                    if member.issym() or member.islnk() or member.isdev():
                        raise NativeArtifactError(f"links/devices forbidden: {member.name}")
                    if member.isdir():
                        (root / relative).mkdir(parents=True, exist_ok=True)
                        continue
                    if not member.isfile():
                        raise NativeArtifactError(f"unsupported archive entry: {member.name}")
                    source = archive.extractfile(member)
                    if source is None:
                        raise NativeArtifactError(f"cannot read: {member.name}")
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            if not (root / "main.py").is_file() or not (root / "deck.csv").is_file():
                raise NativeArtifactError("Kaggle bundle requires root main.py and deck.csv")
            deck = _read_deck(root / "deck.csv")
            bundled = root / "cg" / "libcg.so"
            bundled_sha = _sha256_file(bundled) if bundled.is_file() else None
            if bundled_sha and expected_engine_sha256 and bundled_sha != expected_engine_sha256:
                raise NativeArtifactError("bundle engine SHA does not match uploaded official engine")
            artifact = BundleArtifact(artifact_id, filename, root, _sha256(data), deck, bundled_sha)
            self.bundles[artifact_id] = artifact
            return artifact
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

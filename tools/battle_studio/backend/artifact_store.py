from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

MAX_ENGINE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 128 * 1024 * 1024
MAX_CARD_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000


class ArtifactError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(name: str) -> Path:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ArtifactError(f"unsafe archive path: {name}")
    return Path(*pure.parts)


def _safe_extract_zip(data: bytes, destination: Path) -> list[Path]:
    extracted: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ArtifactError("engine archive has too many members")
        for info in infos:
            if info.is_dir():
                continue
            relative = _safe_relative(info.filename)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return extracted


def _safe_extract_tar(data: bytes, destination: Path) -> list[Path]:
    extracted: list[Path] = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        members = archive.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ArtifactError("bundle has too many members")
        for member in members:
            relative = _safe_relative(member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise ArtifactError(f"links and devices are forbidden: {member.name}")
            if member.isdir():
                (destination / relative).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ArtifactError(f"unsupported archive entry: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise ArtifactError(f"cannot read archive member: {member.name}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return extracted


def _read_deck(path: Path) -> list[int]:
    values: list[int] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    for row in rows:
        if not row:
            continue
        raw = row[0].strip()
        if not raw:
            continue
        if not raw.lstrip("-").isdigit():
            lowered = raw.lower().replace(" ", "_")
            if lowered in {"card_id", "cardid", "id"}:
                continue
            raise ArtifactError(f"deck.csv contains non-integer card id: {raw}")
        values.append(int(raw))
    if len(values) != 60:
        raise ArtifactError(f"deck.csv must contain exactly 60 card IDs, found {len(values)}")
    if any(value <= 0 for value in values):
        raise ArtifactError("deck.csv card IDs must be positive")
    return values


@dataclass(frozen=True)
class EngineArtifact:
    artifact_id: str
    filename: str
    library_path: Path
    sha256: str
    source_kind: str
    compiler: str | None

    def public(self) -> dict[str, Any]:
        return {"id": self.artifact_id, "filename": self.filename, "sha256": self.sha256, "sourceKind": self.source_kind, "compiler": self.compiler}


@dataclass(frozen=True)
class BundleArtifact:
    artifact_id: str
    filename: str
    root: Path
    sha256: str
    deck: tuple[int, ...]
    members: tuple[str, ...]
    bundled_engine_sha256: str | None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.artifact_id,
            "filename": self.filename,
            "sha256": self.sha256,
            "deckCount": len(self.deck),
            "uniqueCardIds": len(set(self.deck)),
            "memberCount": len(self.members),
            "bundledEngineSha256": self.bundled_engine_sha256,
        }


@dataclass
class CardRecord:
    card_id: int
    name: str
    expansion: str = ""
    collection_no: str = ""
    stage_or_type: str = ""
    rule: str = ""
    category: str = ""
    previous_stage: str = ""
    hp: int | None = None
    pokemon_type: str = ""
    weakness: str = ""
    resistance: str = ""
    retreat: str = ""
    link: str = ""
    moves: list[dict[str, Any]] = field(default_factory=list)

    @property
    def basic_energy(self) -> bool:
        return "basic energy" in self.stage_or_type.lower()

    @property
    def ace_spec(self) -> bool:
        text = f"{self.rule} {self.category} {self.stage_or_type}".lower()
        return "ace spec" in text

    def public(self) -> dict[str, Any]:
        return {
            "cardId": self.card_id,
            "name": self.name,
            "expansion": self.expansion,
            "collectionNo": self.collection_no,
            "stageOrType": self.stage_or_type,
            "rule": self.rule,
            "category": self.category,
            "previousStage": self.previous_stage,
            "hp": self.hp,
            "pokemonType": self.pokemon_type,
            "weakness": self.weakness,
            "resistance": self.resistance,
            "retreat": self.retreat,
            "link": self.link,
            "moves": self.moves,
            "basicEnergy": self.basic_energy,
            "aceSpec": self.ace_spec,
        }


@dataclass
class CardCatalog:
    records: dict[int, CardRecord]
    attacks: list[dict[str, Any]]
    source_sha256: dict[str, str]

    def public_summary(self) -> dict[str, Any]:
        return {"cardCount": len(self.records), "attackCount": len(self.attacks), "sourceSha256": self.source_sha256}


class ArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(tempfile.mkdtemp(prefix="black-battle-studio-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.engines: dict[str, EngineArtifact] = {}
        self.bundles: dict[str, BundleArtifact] = {}
        self.card_catalog: CardCatalog | None = None

    def register_engine(self, filename: str, data: bytes) -> EngineArtifact:
        if not data or len(data) > MAX_ENGINE_BYTES:
            raise ArtifactError("engine upload is empty or too large")
        artifact_id = uuid.uuid4().hex
        target_dir = self.root / "engines" / artifact_id
        target_dir.mkdir(parents=True, exist_ok=False)
        compiler: str | None = None
        if data.startswith(b"\x7fELF"):
            library = target_dir / "libcg.so"
            library.write_bytes(data)
            source_kind = "linux-shared-library"
        elif zipfile.is_zipfile(io.BytesIO(data)):
            source_dir = target_dir / "source"
            source_dir.mkdir()
            extracted = _safe_extract_zip(data, source_dir)
            export_files = [path for path in extracted if path.name == "Export.cpp"]
            readmes = [path for path in extracted if path.name == "README.md"]
            licenses = [path for path in extracted if path.name.startswith("LicenseRef-")]
            if len(export_files) != 1 or not readmes or not licenses:
                raise ArtifactError("engine ZIP is not a recognizable official source package")
            source_root = export_files[0].parent
            library = target_dir / "libcg.so"
            cxx = os.environ.get("CXX", "g++")
            command = [cxx, "-std=c++20", "-O2", "-fPIC", "-shared", "Export.cpp", "-o", str(library)]
            try:
                completed = subprocess.run(command, cwd=source_root, check=False, capture_output=True, text=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ArtifactError(f"engine compile failed: {exc}") from exc
            if completed.returncode != 0 or not library.is_file():
                detail = (completed.stderr or completed.stdout)[-4000:]
                raise ArtifactError(f"engine compile failed: {detail}")
            compiler = cxx
            source_kind = "official-source-zip-compiled-locally"
            shutil.rmtree(source_dir, ignore_errors=True)
        else:
            raise ArtifactError("engine must be an ELF libcg.so or official source ZIP")
        artifact = EngineArtifact(artifact_id, filename, library, sha256_file(library), source_kind, compiler)
        self.engines[artifact_id] = artifact
        return artifact

    def register_bundle(self, filename: str, data: bytes, expected_engine_sha256: str | None = None) -> BundleArtifact:
        if not data or len(data) > MAX_BUNDLE_BYTES:
            raise ArtifactError("bundle upload is empty or too large")
        artifact_id = uuid.uuid4().hex
        root = self.root / "bundles" / artifact_id
        root.mkdir(parents=True, exist_ok=False)
        try:
            extracted = _safe_extract_tar(data, root)
            relative = tuple(sorted(path.relative_to(root).as_posix() for path in extracted))
            missing = sorted({"main.py", "deck.csv"} - set(relative))
            if missing:
                raise ArtifactError(f"Kaggle bundle missing root files: {', '.join(missing)}")
            deck = _read_deck(root / "deck.csv")
            bundled_engine = root / "cg" / "libcg.so"
            bundled_sha = sha256_file(bundled_engine) if bundled_engine.is_file() else None
            if bundled_sha and expected_engine_sha256 and bundled_sha != expected_engine_sha256:
                raise ArtifactError("bundle cg/libcg.so does not match the registered official engine SHA-256")
            artifact = BundleArtifact(artifact_id, filename, root, sha256_bytes(data), tuple(deck), relative, bundled_sha)
            self.bundles[artifact_id] = artifact
            return artifact
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def register_card_catalog(self, files: Iterable[tuple[str, bytes]]) -> CardCatalog:
        payloads = {name: data for name, data in files}
        if not payloads or sum(len(value) for value in payloads.values()) > MAX_CARD_BYTES:
            raise ArtifactError("card data upload is empty or too large")
        card_id_name = next((name for name in payloads if name.lower().endswith("card_id_list.csv")), None)
        card_data_name = next((name for name in payloads if name.lower().endswith("en_card_data.csv")), None)
        attack_name = next((name for name in payloads if name.lower().endswith("attack_id_mapping.json")), None)
        if not card_id_name or not card_data_name or not attack_name:
            raise ArtifactError("upload card_id_list.csv, EN_Card_Data.csv, and attack_id_mapping.json together")
        links: dict[int, dict[str, str]] = {}
        with io.StringIO(payloads[card_id_name].decode("utf-8-sig")) as handle:
            for row in csv.DictReader(handle):
                try:
                    links[int(row.get("card_id", ""))] = row
                except ValueError:
                    continue
        records: dict[int, CardRecord] = {}
        with io.StringIO(payloads[card_data_name].decode("utf-8-sig")) as handle:
            for row in csv.DictReader(handle):
                try:
                    card_id = int(row.get("Card ID", ""))
                except ValueError:
                    continue
                record = records.get(card_id)
                if record is None:
                    link = links.get(card_id, {})
                    hp_raw = row.get("HP", "")
                    record = CardRecord(
                        card_id=card_id,
                        name=row.get("Card Name", "") or link.get("card_name", f"Card {card_id}"),
                        expansion=row.get("Expansion", "") or link.get("expansion", ""),
                        collection_no=row.get("Collection No.", "") or link.get("collection_no", ""),
                        stage_or_type=row.get("Stage (Pokémon)/Type (Energy and Trainer)", ""),
                        rule=row.get("Rule", ""), category=row.get("Category", ""), previous_stage=row.get("Previous stage", ""),
                        hp=int(hp_raw) if hp_raw.isdigit() else None,
                        pokemon_type=row.get("Type", ""), weakness=row.get("Weakness", ""), resistance=row.get("Resistance (Type)", ""),
                        retreat=row.get("Retreat", ""), link=link.get("link", ""),
                    )
                    records[card_id] = record
                move_name = row.get("Move Name", "").strip()
                if move_name:
                    record.moves.append({"name": move_name, "cost": row.get("Cost", ""), "damage": row.get("Damage", ""), "text": row.get("Effect Explanation", "")})
        try:
            attacks = json.loads(payloads[attack_name].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArtifactError(f"invalid attack_id_mapping.json: {exc}") from exc
        if not isinstance(attacks, list):
            raise ArtifactError("attack_id_mapping.json must be a JSON array")
        catalog = CardCatalog(records, [value for value in attacks if isinstance(value, dict)], {name: sha256_bytes(data) for name, data in payloads.items()})
        self.card_catalog = catalog
        return catalog

    def list_artifacts(self) -> dict[str, Any]:
        return {
            "engines": [artifact.public() for artifact in self.engines.values()],
            "bundles": [artifact.public() for artifact in self.bundles.values()],
            "cards": self.card_catalog.public_summary() if self.card_catalog else None,
        }

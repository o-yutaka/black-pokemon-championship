from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _worktree_fingerprint(head: str | None, status: str | None) -> str | None:
    if head is None or status is None:
        return None
    payload = f"{head}\n{status}\n".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _runtime_git(repo_root: Path) -> dict[str, Any]:
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    head = _git(repo_root, "rev-parse", "HEAD")
    return {
        "repoRoot": str(repo_root),
        "branch": _git(repo_root, "branch", "--show-current"),
        "head": head,
        "dirty": None if status is None else bool(status),
        "dirtyEntryCount": None if status is None else len(status.splitlines()),
        "worktreeFingerprint": _worktree_fingerprint(head, status),
    }


def _frontend_build(frontend_dist: Path, runtime_git: Mapping[str, Any]) -> dict[str, Any]:
    built_head = os.environ.get("BLACK_FRONTEND_BUILD_HEAD") or None
    built_branch = os.environ.get("BLACK_FRONTEND_BUILD_BRANCH") or None
    built_dirty_raw = os.environ.get("BLACK_FRONTEND_BUILD_DIRTY")
    built_dirty = None if built_dirty_raw is None else built_dirty_raw == "1"
    built_at = os.environ.get("BLACK_FRONTEND_BUILT_AT") or None
    built_fingerprint = os.environ.get("BLACK_FRONTEND_BUILD_FINGERPRINT") or None
    runtime_fingerprint = runtime_git.get("worktreeFingerprint")
    provenance_known = built_head is not None and built_dirty is not None and built_fingerprint is not None
    matches_runtime = bool(
        provenance_known
        and runtime_fingerprint
        and built_fingerprint == runtime_fingerprint
    )
    index_path = frontend_dist / "index.html"
    return {
        "exists": frontend_dist.is_dir(),
        "indexExists": index_path.is_file(),
        "indexSha256": _sha256(index_path),
        "builtAt": built_at,
        "gitHead": built_head,
        "gitBranch": built_branch,
        "gitDirty": built_dirty,
        "worktreeFingerprint": built_fingerprint,
        "provenanceKnown": provenance_known,
        "matchesRuntimeWorktree": matches_runtime,
    }


def _active_sessions(sessions: Mapping[str, Any]) -> dict[str, int]:
    counts = {
        "total": 0,
        "emulator": 0,
        "officialProcess": 0,
        "officialNative": 0,
        "unknown": 0,
    }
    for session in sessions.values():
        counts["total"] += 1
        if getattr(session, "public_view", None) is None:
            engine_name = str(getattr(getattr(session, "engine", None), "name", ""))
            if "emulator" in engine_name.lower():
                counts["emulator"] += 1
            else:
                counts["unknown"] += 1
        elif getattr(session, "public_advance", None) == "agent":
            counts["officialNative"] += 1
        elif getattr(session, "public_advance", None) == "legal-first":
            counts["officialProcess"] += 1
        else:
            counts["unknown"] += 1
    return counts


def build_health(live_server: Any) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_git = _runtime_git(repo_root)
    frontend_build = _frontend_build(live_server.FRONTEND_DIST, runtime_git)
    official_process = bool(live_server._runner_available())
    native_engine_count = len(live_server.NATIVE.engines)
    official_start_available = official_process or native_engine_count > 0
    simulator_allowed = bool(live_server._simulator_view_available())
    card_catalog_available = bool(live_server._card_catalog_available())
    active_sessions = _active_sessions(live_server.SESSIONS)

    warnings: list[str] = []
    if not official_start_available:
        warnings.append("OFFICIAL_RUNTIME_UNAVAILABLE")
    if not frontend_build["indexExists"]:
        warnings.append("FRONTEND_BUILD_MISSING")
    elif not frontend_build["provenanceKnown"]:
        warnings.append("FRONTEND_BUILD_PROVENANCE_UNKNOWN")
    elif not frontend_build["matchesRuntimeWorktree"]:
        warnings.append("FRONTEND_BUILD_DOES_NOT_MATCH_RUNTIME_WORKTREE")
    if runtime_git["dirty"]:
        warnings.append("RUNTIME_WORKTREE_DIRTY")

    legacy = {
        "emulator": True,
        "officialCabt": official_start_available,
        "officialProcessRunner": official_process,
        "nativeOfficialEngineCount": native_engine_count,
        "nativeBundleCount": len(live_server.NATIVE.bundles),
        "cardCatalog": card_catalog_available,
        "frontendDist": live_server.FRONTEND_DIST.is_dir(),
        "publicView": live_server.PUBLIC_PROTOCOL_VERSION,
        "simulatorView": simulator_allowed,
        "pid": os.getpid(),
    }

    return {
        "ok": True,
        "service": "black-battle-studio-live-bridge",
        "healthSchemaVersion": "2.1",
        "fieldSemantics": {
            "emulator": "capability_available_not_active_session",
            "officialCabt": "new_official_session_start_available_not_current_session",
            "frontendDist": "directory_exists_not_source_match",
        },
        **legacy,
        "legacyFieldsDeprecated": sorted(legacy),
        "capabilities": {
            "emulatorAvailable": True,
            "officialProcessRunnerAvailable": official_process,
            "nativeOfficialEngineCount": native_engine_count,
            "officialSessionStartAvailable": official_start_available,
            "simulatorViewAllowed": simulator_allowed,
            "cardCatalogAvailable": card_catalog_available,
            "publicViewProtocol": live_server.PUBLIC_PROTOCOL_VERSION,
        },
        "activeSessions": active_sessions,
        "runtime": {
            "pid": os.getpid(),
            "cwd": str(Path.cwd()),
            "git": runtime_git,
            "frontendBuild": frontend_build,
        },
        "artifacts": {
            "nativeBundleCount": len(live_server.NATIVE.bundles),
        },
        "warnings": warnings,
        "legacy": legacy,
    }

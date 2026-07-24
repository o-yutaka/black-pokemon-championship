from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bundle_manager import BundleError, BundleStore
from card_catalog import get_catalog
from emulator_engine import CabtShapeEmulator
from native_artifacts import NativeArtifactError, NativeArtifactStore
from native_official_engine import NativeEngineError, NativeOfficialBattleSession
from official_engine import OfficialEngineError, OfficialProcessEngine


class Engine(Protocol):
    name: str
    async def start(self) -> dict[str, Any]: ...
    async def step(self, selection: list[int]) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    def legal_selections(self) -> list[list[int]]: ...


class SessionRequest(BaseModel):
    engine: str = "emulator"
    bundleId: str | None = None
    opponentBundleId: str | None = None
    engineId: str | None = None
    playerBundleId: str | None = None
    nativeOpponentBundleId: str | None = None


@dataclass
class Session:
    engine: Engine
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    frame: dict[str, Any] | None = None


app = FastAPI(title="BLACK Battle Studio Live Bridge", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "https://o-yutaka.github.io"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
SESSIONS: dict[str, Session] = {}
BUNDLES = BundleStore(Path(os.environ.get("BLACK_BUNDLE_ROOT", Path(tempfile.gettempdir()) / "black-battle-studio-bundles")))
NATIVE = NativeArtifactStore(Path(os.environ.get("BLACK_NATIVE_RUNTIME_ROOT", Path(tempfile.gettempdir()) / "black-battle-studio-native")))
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _runner_available() -> bool:
    return bool(os.environ.get("BLACK_OFFICIAL_RUNNER"))


def _card_catalog_available() -> bool:
    try:
        get_catalog()
        return True
    except (FileNotFoundError, OSError, ValueError):
        return False


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "black-battle-studio-live-bridge",
        "emulator": True,
        "officialCabt": _runner_available() or bool(NATIVE.engines),
        "officialProcessRunner": _runner_available(),
        "nativeOfficialEngineCount": len(NATIVE.engines),
        "nativeBundleCount": len(NATIVE.bundles),
        "cardCatalog": _card_catalog_available(),
        "frontendDist": FRONTEND_DIST.is_dir(),
        "pid": os.getpid(),
    }


@app.get("/api/cards")
async def card_catalog() -> dict[str, Any]:
    try:
        cards, sources = get_catalog()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"card catalog failed: {exc}") from exc
    return {"ok": True, "count": len(cards), "sources": [path.name for path in sources], "cards": cards}


@app.post("/api/bundles")
async def upload_bundle(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        info = BUNDLES.ingest(file.file, file.filename or "bundle.tgz")
    except BundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    return {"ok": True, **info.as_dict()}


@app.get("/api/bundles/{bundle_id}")
async def bundle_info(bundle_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, **BUNDLES.get(bundle_id).as_dict()}
    except BundleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/native/engine")
async def upload_native_engine(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        artifact = NATIVE.register_engine(file.filename or "engine", await file.read())
        return {"ok": True, "engine": artifact.public()}
    except (NativeArtifactError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/native/bundles")
async def upload_native_bundle(file: UploadFile = File(...), engine_id: str | None = None) -> dict[str, Any]:
    try:
        expected = None
        if engine_id:
            engine = NATIVE.engines.get(engine_id)
            if engine is None:
                raise NativeArtifactError("unknown native engine id")
            expected = engine.sha256
        artifact = NATIVE.register_bundle(file.filename or "bundle.tgz", await file.read(), expected)
        return {"ok": True, "bundle": artifact.public(), "deck": list(artifact.deck)}
    except (NativeArtifactError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/native/artifacts")
async def native_artifacts() -> dict[str, Any]:
    return {"ok": True, "engines": [item.public() for item in NATIVE.engines.values()], "bundles": [item.public() for item in NATIVE.bundles.values()]}


@app.post("/api/sessions")
async def create_session(request: SessionRequest) -> dict[str, Any]:
    try:
        if request.engine == "emulator":
            engine: Engine = CabtShapeEmulator()
        elif request.engine == "official":
            if not request.bundleId:
                raise HTTPException(status_code=422, detail="bundleId is required")
            player = BUNDLES.get(request.bundleId)
            opponent = BUNDLES.get(request.opponentBundleId) if request.opponentBundleId else None
            engine = OfficialProcessEngine(player.root, opponent.root if opponent else None)
        elif request.engine == "official-native":
            if not request.engineId or not request.playerBundleId or not request.nativeOpponentBundleId:
                raise HTTPException(status_code=422, detail="engineId, playerBundleId and nativeOpponentBundleId are required")
            engine_artifact = NATIVE.engines.get(request.engineId)
            player = NATIVE.bundles.get(request.playerBundleId)
            opponent = NATIVE.bundles.get(request.nativeOpponentBundleId)
            if not engine_artifact or not player or not opponent:
                raise HTTPException(status_code=404, detail="unknown native engine or bundle artifact")
            engine = NativeOfficialBattleSession(engine_artifact, (player, opponent))
        else:
            raise HTTPException(status_code=400, detail="engine must be emulator, official or official-native")
        frame = await engine.start()
    except BundleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OfficialEngineError, NativeEngineError, NativeArtifactError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = Session(engine=engine, frame=frame)
    return {"sessionId": session_id, "engine": engine.name, "wsPath": f"/ws/battle/{session_id}"}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    session = SESSIONS.pop(session_id, None)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    await session.engine.close()
    return {"deleted": True, "sessionId": session_id}


async def _snapshot_payload(session_id: str, session: Session) -> dict[str, Any]:
    assert session.frame is not None
    return {"type": "snapshot", "sessionId": session_id, "engine": session.engine.name, "frame": session.frame, "legalSelections": session.engine.legal_selections()}


@app.websocket("/ws/battle/{session_id}")
async def battle_socket(websocket: WebSocket, session_id: str) -> None:
    session = SESSIONS.get(session_id)
    if session is None:
        await websocket.close(code=4404, reason="unknown session")
        return
    await websocket.accept()
    await websocket.send_json(await _snapshot_payload(session_id, session))
    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong", "sessionId": session_id})
                continue
            if message_type == "close":
                await websocket.send_json({"type": "closed", "sessionId": session_id})
                await websocket.close(code=1000)
                break
            if message_type == "destroy":
                await session.engine.close()
                SESSIONS.pop(session_id, None)
                await websocket.send_json({"type": "closed", "sessionId": session_id})
                await websocket.close(code=1000)
                break
            if message_type != "step":
                await websocket.send_json({"type": "error", "code": "UNSUPPORTED_MESSAGE"})
                continue
            selection = message.get("selection")
            if not isinstance(selection, list) or any(not isinstance(value, int) for value in selection):
                await websocket.send_json({"type": "error", "code": "INVALID_SELECTION"})
                continue
            try:
                async with session.lock:
                    session.frame = await session.engine.step(selection)
                await websocket.send_json(await _snapshot_payload(session_id, session))
            except (ValueError, OfficialEngineError, NativeEngineError) as exc:
                await websocket.send_json({"type": "error", "code": "ENGINE_REJECTED", "detail": str(exc)})
    except WebSocketDisconnect:
        return


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="battle-studio")

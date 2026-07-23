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
from emulator_engine import CabtShapeEmulator
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


@dataclass
class Session:
    engine: Engine
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    frame: dict[str, Any] | None = None


app = FastAPI(title="BLACK Battle Studio Live Bridge", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "https://o-yutaka.github.io"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
SESSIONS: dict[str, Session] = {}
BUNDLES = BundleStore(Path(os.environ.get("BLACK_BUNDLE_ROOT", Path(tempfile.gettempdir()) / "black-battle-studio-bundles")))
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _official_available() -> bool:
    return bool(os.environ.get("BLACK_OFFICIAL_RUNNER"))


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "black-battle-studio-live-bridge", "emulator": True, "officialCabt": _official_available(), "frontendDist": FRONTEND_DIST.is_dir(), "pid": os.getpid()}


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
        else:
            raise HTTPException(status_code=400, detail="engine must be emulator or official")
        frame = await engine.start()
    except BundleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OfficialEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = Session(engine=engine, frame=frame)
    return {"sessionId": session_id, "engine": engine.name, "wsPath": f"/ws/battle/{session_id}"}


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
            except (ValueError, OfficialEngineError) as exc:
                await websocket.send_json({"type": "error", "code": "ENGINE_REJECTED", "detail": str(exc)})
    except WebSocketDisconnect:
        return


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="battle-studio")

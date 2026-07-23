from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from artifact_store import ArtifactError, ArtifactStore
from emulator_engine import CabtShapeEmulator
from official_engine import EngineRuntimeError, OfficialBattleSession


class LiveEngine(Protocol):
    name: str
    async def start(self) -> dict[str, Any]: ...
    async def step(self, selection: list[int] | None = None) -> dict[str, Any]: ...
    async def close(self) -> None: ...
    def legal_selections(self) -> list[list[int]]: ...


class SessionRequest(BaseModel):
    engine: str = "emulator"
    engine_id: str | None = None
    player_bundle_id: str | None = None
    opponent_bundle_id: str | None = None


@dataclass
class Session:
    engine: LiveEngine
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    frame: dict[str, Any] | None = None


app = FastAPI(title="BLACK Battle Studio Live Bridge", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "https://o-yutaka.github.io"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
SESSIONS: dict[str, Session] = {}
ARTIFACTS = ArtifactStore(Path(os.environ.get("BLACK_STUDIO_ARTIFACT_ROOT", "/tmp/black-battle-studio-artifacts")))
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ArtifactError, EngineRuntimeError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True, "service": "black-battle-studio-live-bridge", "emulator": True,
        "officialCabt": bool(ARTIFACTS.engines), "frontendDist": FRONTEND_DIST.is_dir(),
        "pid": os.getpid(), "artifacts": ARTIFACTS.list_artifacts(),
    }


@app.get("/api/artifacts")
async def artifacts() -> dict[str, Any]:
    return ARTIFACTS.list_artifacts()


@app.post("/api/artifacts/engine")
async def upload_engine(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        artifact = await asyncio.to_thread(ARTIFACTS.register_engine, file.filename or "engine", await file.read())
        return {"engine": artifact.public()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/artifacts/bundles")
async def upload_bundle(file: UploadFile = File(...), engine_id: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        expected = ARTIFACTS.engines[engine_id].sha256 if engine_id and engine_id in ARTIFACTS.engines else None
        artifact = await asyncio.to_thread(ARTIFACTS.register_bundle, file.filename or "submission.tgz", await file.read(), expected)
        return {"bundle": artifact.public(), "deck": list(artifact.deck)}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/artifacts/cards")
async def upload_cards(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    try:
        payloads = [(file.filename or "unknown", await file.read()) for file in files]
        catalog = await asyncio.to_thread(ARTIFACTS.register_card_catalog, payloads)
        return {"cards": catalog.public_summary()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/cards")
async def cards(q: str = "", limit: int = Query(default=2000, ge=1, le=5000)) -> dict[str, Any]:
    catalog = ARTIFACTS.card_catalog
    if catalog is None:
        raise HTTPException(status_code=404, detail="card catalog not uploaded")
    query = q.strip().lower()
    records = list(catalog.records.values())
    if query:
        records = [record for record in records if query in f"{record.card_id} {record.name} {record.expansion} {record.stage_or_type} {record.category} {record.pokemon_type}".lower()]
    records.sort(key=lambda record: record.card_id)
    return {"cards": [record.public() for record in records[:limit]], "total": len(records), "catalog": catalog.public_summary()}


@app.get("/api/engine/{engine_id}/catalog")
async def engine_catalog(engine_id: str) -> dict[str, Any]:
    artifact = ARTIFACTS.engines.get(engine_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="unknown engine")
    try:
        from official_engine import OfficialLibrary
        library = await asyncio.to_thread(OfficialLibrary, artifact)
        return {"cards": library.all_cards(), "attacks": library.all_attacks(), "engine": artifact.public()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/sessions")
async def create_session(request: SessionRequest) -> dict[str, Any]:
    try:
        if request.engine == "emulator":
            engine: LiveEngine = CabtShapeEmulator()
        elif request.engine == "official":
            if not request.engine_id or not request.player_bundle_id or not request.opponent_bundle_id:
                raise ArtifactError("official session requires engine_id, player_bundle_id, and opponent_bundle_id")
            engine_artifact = ARTIFACTS.engines.get(request.engine_id)
            player = ARTIFACTS.bundles.get(request.player_bundle_id)
            opponent = ARTIFACTS.bundles.get(request.opponent_bundle_id)
            if not engine_artifact or not player or not opponent:
                raise ArtifactError("unknown engine or bundle artifact")
            for bundle in (player, opponent):
                if bundle.bundled_engine_sha256 and bundle.bundled_engine_sha256 != engine_artifact.sha256:
                    raise ArtifactError(f"{bundle.filename} contains a different cg/libcg.so")
            engine = await asyncio.to_thread(OfficialBattleSession, engine_artifact, (player, opponent))
        else:
            raise ArtifactError(f"unsupported engine mode: {request.engine}")
        frame = await engine.start()
        session_id = uuid.uuid4().hex
        SESSIONS[session_id] = Session(engine=engine, frame=frame)
        return {"sessionId": session_id, "engine": engine.name, "wsPath": f"/ws/battle/{session_id}"}
    except Exception as exc:
        raise _http_error(exc) from exc


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
                await session.engine.close()
                SESSIONS.pop(session_id, None)
                await websocket.send_json({"type": "closed", "sessionId": session_id})
                await websocket.close(code=1000)
                break
            if message_type != "step":
                await websocket.send_json({"type": "error", "code": "UNSUPPORTED_MESSAGE"})
                continue
            selection = message.get("selection")
            if selection is not None and (not isinstance(selection, list) or any(not isinstance(value, int) for value in selection)):
                await websocket.send_json({"type": "error", "code": "INVALID_SELECTION"})
                continue
            try:
                async with session.lock:
                    session.frame = await session.engine.step(selection)
                await websocket.send_json(await _snapshot_payload(session_id, session))
            except (ValueError, EngineRuntimeError) as exc:
                await websocket.send_json({"type": "error", "code": "ENGINE_REJECTED", "detail": str(exc)})
    except WebSocketDisconnect:
        return


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="battle-studio")

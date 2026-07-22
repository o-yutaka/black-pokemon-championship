from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from emulator_engine import CabtShapeEmulator


class SessionRequest(BaseModel):
    engine: str = "emulator"


@dataclass
class Session:
    engine: CabtShapeEmulator
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    frame: dict[str, Any] | None = None


app = FastAPI(title="BLACK Battle Studio Live Bridge", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
SESSIONS: dict[str, Session] = {}
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _official_available() -> bool:
    try:
        import cg.game  # type: ignore # noqa: F401
        return True
    except Exception:
        return False


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "black-battle-studio-live-bridge",
        "emulator": True,
        "officialCabt": _official_available(),
        "frontendDist": FRONTEND_DIST.is_dir(),
        "pid": os.getpid(),
    }


@app.post("/api/sessions")
async def create_session(request: SessionRequest) -> dict[str, Any]:
    if request.engine != "emulator":
        raise HTTPException(status_code=400, detail="official engine requires WSL2 CABT adapter configuration")
    engine = CabtShapeEmulator()
    frame = await engine.start()
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = Session(engine=engine, frame=frame)
    return {"sessionId": session_id, "engine": engine.name, "wsPath": f"/ws/battle/{session_id}"}


async def _snapshot_payload(session_id: str, session: Session) -> dict[str, Any]:
    assert session.frame is not None
    return {
        "type": "snapshot",
        "sessionId": session_id,
        "engine": session.engine.name,
        "frame": session.frame,
        "legalSelections": session.engine.legal_selections(),
    }


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
            except ValueError as exc:
                await websocket.send_json({"type": "error", "code": "ENGINE_REJECTED", "detail": str(exc)})
    except WebSocketDisconnect:
        return


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="battle-studio")

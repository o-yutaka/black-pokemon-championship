from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / ".github/workflows/privacy-hardening-autopatch.yml"


def extracted_script() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start_marker = "          python - <<'PY'\n"
    end_marker = "\n          PY\n\n      - name: Commit patched implementation"
    start = source.index(start_marker) + len(start_marker)
    end = source.index(end_marker, start)
    lines = source[start:end].splitlines()
    script = "\n".join(line[10:] if line.startswith("          ") else line for line in lines) + "\n"

    bad_start = script.index("old_create_tail =")
    bad_end_marker = "replace_once(live, old_create_tail, new_create_tail)"
    bad_end = script.index(bad_end_marker, bad_start) + len(bad_end_marker)
    new_tail = '''    except BundleError as exc:
        if request.engine in {"official", "official-native"}:
            LOGGER.info("official bundle lookup failed: %s", exc)
            raise HTTPException(status_code=404, detail="選択したBundleを確認してください。") from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OfficialEngineError, NativeEngineError, NativeArtifactError, OSError, ValueError) as exc:
        if request.engine in {"official", "official-native"}:
            LOGGER.exception("official runtime session creation failed")
            raise HTTPException(status_code=503, detail="公式対戦を開始できませんでした。BundleとEngineの整合を確認してください。") from exc
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if request.subjectPlayer not in (0, 1):
        await engine.close()
        raise HTTPException(status_code=422, detail="subjectPlayer must be 0 or 1")
    session_id = uuid.uuid4().hex
    is_public = request.engine in {"official", "official-native"}
    public_view = PublicBattleView(session_id, subject_player=request.subjectPlayer) if is_public else None
    public_advance = "legal-first" if request.engine == "official" else "agent" if request.engine == "official-native" else None
    SESSIONS[session_id] = Session(engine=engine, frame=frame, public_view=public_view, public_advance=public_advance)
    asyncio.create_task(_expire_session(session_id))
    public_engine = "official-battle" if is_public else engine.name
    return {
        "sessionId": session_id,
        "engine": public_engine,
        "wsPath": f"/ws/battle/{session_id}",
        "publicProtocol": PUBLIC_PROTOCOL_VERSION if is_public else None,
        "viewPolicy": "player_view" if is_public else "spectator",
        "subjectPlayer": request.subjectPlayer,
    }
'''
    robust = f'''text = live.read_text(encoding="utf-8")
create_start = text.index('    except BundleError as exc:', text.index('@app.post("/api/sessions")'))
create_end = text.index('\\n\\n@app.delete("/api/sessions/{{session_id}}")', create_start)
new_create_tail = {new_tail!r}
live.write_text(text[:create_start] + new_create_tail + text[create_end:], encoding="utf-8")'''
    return script[:bad_start] + robust + script[bad_end:]


def main() -> None:
    script = extracted_script()
    namespace = {"__name__": "__main__", "__file__": str(SOURCE)}
    exec(compile(script, str(SOURCE), "exec"), namespace, namespace)


if __name__ == "__main__":
    main()

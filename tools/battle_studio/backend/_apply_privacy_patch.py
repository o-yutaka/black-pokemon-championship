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

    create_start = script.index("old_create_tail =")
    create_end_marker = "replace_once(live, old_create_tail, new_create_tail)"
    create_end = script.index(create_end_marker, create_start) + len(create_end_marker)
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
    robust_create = f'''text = live.read_text(encoding="utf-8")
create_start = text.index('    except BundleError as exc:', text.index('@app.post("/api/sessions")'))
create_end = text.index('\\n\\n@app.delete("/api/sessions/{{session_id}}")', create_start)
new_create_tail = {new_tail!r}
live.write_text(text[:create_start] + new_create_tail + text[create_end:], encoding="utf-8")'''
    script = script[:create_start] + robust_create + script[create_end:]

    card_start = script.index('card_art = root / "tools/battle_studio/frontend/src/cardArt.ts"')
    workflow_start = script.index('workflow = root / ".github/workflows/battle-studio-live-ci.yml"', card_start)
    new_card_block = '''      const wanted = new Set(idKey.split(",").map(Number));
      const persistentCache = readCache();
      const displayCache = { ...persistentCache };
      const supplied = publicCards.filter((card) => wanted.has(card.id));
      await resolveCards(supplied, displayCache, controller.signal);
      const suppliedIds = new Set(supplied.map((card) => card.id));
      const unresolved = new Set([...wanted].filter((id) => !suppliedIds.has(id)));
      if (unresolved.size) {
        const response = await fetch("/api/cards", { signal: controller.signal, cache: "force-cache" });
        if (response.ok) {
          const payload = await response.json() as unknown;
          const rows: CatalogCard[] = [];
          for (const row of collectRows(payload)) {
            const record = asRecord(row);
            if (!record) continue;
            const id = pickNumber(record);
            if (id === null || !unresolved.has(id)) continue;
            const explicit = pickUrl(record);
            if (explicit) displayCache[String(id)] = explicit;
            rows.push({ id, name: text(record, "name", "card_name", "Card Name"), number: text(record, "number", "collection_no", "Collection No."), expansion: text(record, "expansion", "Expansion"), sourceLink: text(record, "sourceLink", "link") });
          }
          await resolveCards(rows, displayCache, controller.signal);
          for (const id of unresolved) {
            const url = displayCache[String(id)];
            if (url) persistentCache[String(id)] = url;
          }
        }
      }
      localStorage.setItem(CACHE_KEY, JSON.stringify(persistentCache));
      setEntries(Object.entries(displayCache).map(([id, url]) => [Number(id), url]));
'''
    robust_card = f'''card_art = root / "tools/battle_studio/frontend/src/cardArt.ts"
card_text = card_art.read_text(encoding="utf-8")
card_start = card_text.index('      const wanted = new Set(idKey.split(",").map(Number));')
card_end = card_text.index('    }})().catch(() => undefined);', card_start)
new_card_block = {new_card_block!r}
card_art.write_text(card_text[:card_start] + new_card_block + card_text[card_end:], encoding="utf-8")'''

    required = '''              "clean_close_pass",
              "session_cleanup_pass",
              "official_public_session_create_pass",
              "official_public_snapshot_pass",
              "official_raw_identifiers_absent",
              "official_step_contract_hidden",
              "official_advance_pass",
              "official_session_cleanup_pass",
'''
    robust_workflow = f'''workflow = root / ".github/workflows/battle-studio-live-ci.yml"
workflow_text = workflow.read_text(encoding="utf-8")
old_required = '              "clean_close_pass",\\n              "reconnect_latest_snapshot_pass",\\n'
if old_required not in workflow_text:
    raise SystemExit("live CI required-check block was not found")
new_required = {required!r}
workflow.write_text(workflow_text.replace(old_required, new_required), encoding="utf-8")'''
    return script[:card_start] + robust_card + "\n\n" + robust_workflow + "\n"


def main() -> None:
    script = extracted_script()
    namespace = {"__name__": "__main__", "__file__": str(SOURCE)}
    exec(compile(script, str(SOURCE), "exec"), namespace, namespace)


if __name__ == "__main__":
    main()
